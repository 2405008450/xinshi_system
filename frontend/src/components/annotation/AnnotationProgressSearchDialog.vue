<template>
  <DraggableFormDialog
    v-model="visible"
    title="项目进度记录"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    class="annotation-progress-search-dialog"
    @closed="$emit('closed')"
  >
    <AppForm :inline="true" :model="filters" class="progress-search-form">
      <el-form-item label="关键词" class="progress-search-keyword">
        <el-input
          v-model="filters.keyword"
          clearable
          maxlength="100"
          placeholder="检索具体进度或状态变更说明"
          @input="handleKeywordInput"
          @keyup.enter="search(true, false)"
        />
      </el-form-item>
      <el-form-item label="节点时间" class="progress-search-range">
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :clearable="false"
          @change="handleRangeChange"
        />
      </el-form-item>
      <el-form-item label="显示" class="progress-search-page-size">
        <el-select v-model="pageSizeMode" @change="handlePageSizeChange">
          <el-option v-for="option in PAGE_SIZE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item class="progress-search-actions">
        <el-button type="primary" :disabled="!canSearch" @click="search(true, false)">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </AppForm>

    <div class="progress-search-hint">默认按填写时间展示最近提交的记录；关键词检索默认查询最近 3 个月，单次时间范围最多 366 天。</div>
    <div class="progress-search-summary">
      <template v-if="pageSizeMode === 'all'">
        {{ allLoaded ? `已加载全部 ${pagination.total} 条记录` : `已加载 ${rows.length} / 总计 ${pagination.total} 条记录` }}
      </template>
      <template v-else>共找到 {{ pagination.total }} 条记录</template>
    </div>

    <div ref="resultsRef" v-loading="loading" class="progress-search-results">
      <template v-if="rows.length">
        <article v-for="row in rows" :key="row.id" class="progress-search-item">
          <div class="progress-search-item__header">
            <div class="progress-search-project">
              <b>{{ row.projectOrderNo }}</b>
              <span>{{ row.projectName || '未命名项目' }}</span>
            </div>
            <el-button type="primary" link @click="emit('open-context', row)">查看上下文</el-button>
          </div>
          <div class="progress-search-item__content">
            <template v-for="(segment, index) in highlight(row.changeNote)" :key="`${row.id}:${index}`">
              <mark v-if="segment.matched">{{ segment.text }}</mark><span v-else>{{ segment.text }}</span>
            </template>
          </div>
          <div class="progress-search-item__meta">
            <el-tag size="small" effect="plain">{{ row.recordType === 'progress' ? '具体进度' : '状态变更' }}</el-tag>
            <el-tag size="small" :type="statusType(row.toStatus)">{{ statusLabel(row.toStatus) }}</el-tag>
            <span>客户经理：{{ row.clientManagerName || '未分配' }}</span>
            <span>项目经理：{{ row.projectManagerName || '未分配' }}</span>
            <span>节点时间：{{ formatDateTime(row.effectiveOn) }}</span>
            <span>填写时间：{{ formatDateTime(row.changedAt) }}</span>
            <span>填写人：{{ row.changedByName || '系统' }}</span>
          </div>
        </article>
      </template>
      <el-empty
        v-else-if="!loading"
        :description="viewMode === 'recent' ? '暂无已提交的进度记录' : '当前条件下未找到进度记录'"
        :image-size="80"
      />
    </div>

    <div v-if="pageSizeMode === 'all' && rows.length" class="progress-search-load-more">
      <el-button v-if="allLoadError" type="primary" link @click="retryLoadAll">加载失败，点击重试</el-button>
      <span v-else-if="appendLoading">正在加载更多记录…</span>
      <span v-else-if="allLoaded">已加载全部记录</span>
      <span v-else ref="allLoadSentinel">继续向下滚动以加载更多</span>
    </div>

    <el-pagination
      v-if="pageSizeMode !== 'all' && pagination.total > pagination.limit"
      v-model:current-page="pagination.page"
      :page-size="pagination.limit"
      :total="pagination.total"
      layout="total, prev, pager, next, jumper"
      class="progress-search-pagination"
      @current-change="handlePageChange"
    />
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as annotationOpsApi from '@/api/annotationOps'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { defaultProgressSearchRange, isProgressSearchRangeValid, splitKeywordMatches } from '@/utils/annotationProgressSearch'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'open-context', 'closed'])
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })

const PAGE_SIZE_OPTIONS = [
  { value: 10, label: '10 条/页' },
  { value: 20, label: '20 条/页' },
  { value: 50, label: '50 条/页' },
  { value: 100, label: '100 条/页' },
  { value: 'all', label: '全部（逐步加载）' },
]
const ALL_BATCH_SIZE = 100
const STATUS_LABELS = {
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果', resource_sourcing: '资源开拓',
  resource_sourcing_cancelled: '取消资源开拓', trial_preparation: '试标准备', trial_in_progress: '试标中', trial_submitted: '试标已提交',
  trial_passed: '试标通过', trial_failed: '试标未通过', trial_partially_passed: '部分试标通过',
  project_in_progress: '项目进行中', sent_to_client: '已发客户', client_feedback: '客户反馈',
  cancelled: '已取消', partially_cancelled: '已部分取消', paused: '暂停', actively_abandoned: '主动放弃',
}
const filters = reactive({ keyword: '', dateRange: defaultProgressSearchRange() })
const pagination = reactive({ page: 1, limit: 10, total: 0 })
const pageSizeMode = ref(10)
const rows = ref([])
const loading = ref(false)
const appendLoading = ref(false)
const allLoadError = ref(false)
const viewMode = ref('recent')
const resultsRef = ref(null)
const allLoadSentinel = ref(null)
let searchTimer
let requestController
let requestId = 0
let preserveOnNextOpen = false
let allLoadObserver

const canSearch = computed(() => Boolean(filters.keyword.trim()) && isProgressSearchRangeValid(filters.dateRange))
const allLoaded = computed(() => rows.value.length >= pagination.total)
const statusLabel = (value) => STATUS_LABELS[value] || value || '-'
const statusType = (value) => ({
  initial_consultation: 'info', consultation_no_result: 'info', resource_sourcing: 'primary',
  resource_sourcing_cancelled: 'danger', trial_preparation: 'warning', trial_in_progress: 'warning', trial_submitted: 'primary',
  trial_passed: 'success', trial_failed: 'danger', trial_partially_passed: 'warning', project_in_progress: 'primary',
  sent_to_client: 'success', client_feedback: 'warning', cancelled: 'danger', partially_cancelled: 'warning',
  paused: 'warning', actively_abandoned: 'danger',
}[value] || 'info')
const highlight = (content) => splitKeywordMatches(content, filters.keyword)

const cancelRequest = () => {
  requestController?.abort()
  requestId += 1
  loading.value = false
  appendLoading.value = false
}

const clearResults = () => {
  cancelRequest()
  rows.value = []
  pagination.total = 0
  allLoadError.value = false
}

const requestPage = async ({ mode = viewMode.value, append = false } = {}) => {
  if (append && (appendLoading.value || allLoaded.value || allLoadError.value)) return
  requestController?.abort()
  requestController = new AbortController()
  const current = ++requestId
  const limit = pageSizeMode.value === 'all' ? ALL_BATCH_SIZE : pagination.limit
  const skip = pageSizeMode.value === 'all'
    ? (append ? rows.value.length : 0)
    : (pagination.page - 1) * limit
  viewMode.value = mode
  if (append) {
    appendLoading.value = true
  } else {
    rows.value = []
    pagination.total = 0
    allLoadError.value = false
    loading.value = true
  }
  try {
    const config = { signal: requestController.signal }
    const page = mode === 'search'
      ? await annotationOpsApi.searchStatusHistory({
          keyword: filters.keyword.trim(),
          dateFrom: filters.dateRange[0],
          dateTo: filters.dateRange[1],
          skip,
          limit,
        }, config)
      : await annotationOpsApi.getRecentStatusHistory({ skip, limit }, config)
    if (current !== requestId) return
    const items = Array.isArray(page?.items) ? page.items : []
    if (append) {
      const existingIds = new Set(rows.value.map((item) => String(item.id)))
      rows.value = [...rows.value, ...items.filter((item) => !existingIds.has(String(item.id)))]
    } else {
      rows.value = items
    }
    pagination.total = Number(page?.total || 0)
  } catch (error) {
    if (current !== requestId || error?.code === 'ERR_CANCELED') return
    if (append) {
      allLoadError.value = true
      ElMessage.error(error?.detail || '后续进度记录加载失败，可点击重试')
    } else {
      rows.value = []
      pagination.total = 0
      ElMessage.error(error?.detail || (mode === 'search' ? '项目进度检索失败，请稍后重试' : '最近进度记录加载失败，请稍后重试'))
    }
  } finally {
    if (current === requestId) {
      loading.value = false
      appendLoading.value = false
    }
  }
}

const loadRecent = async (resetPage = true) => {
  clearTimeout(searchTimer)
  if (resetPage) pagination.page = 1
  return requestPage({ mode: 'recent' })
}

const search = async (resetPage = true, silent = false) => {
  clearTimeout(searchTimer)
  if (!filters.keyword.trim()) return loadRecent(resetPage)
  if (!isProgressSearchRangeValid(filters.dateRange)) {
    clearResults()
    viewMode.value = 'search'
    if (!silent) ElMessage.warning('请选择不超过 366 天的有效时间范围')
    return
  }
  if (resetPage) pagination.page = 1
  return requestPage({ mode: 'search' })
}

const handleKeywordInput = (value) => {
  clearTimeout(searchTimer)
  if (!value?.trim()) return loadRecent(true)
  searchTimer = setTimeout(() => search(true, true), 400)
}
const handleRangeChange = () => {
  if (!filters.keyword.trim()) return
  search(true, true)
}
const handlePageSizeChange = () => {
  pagination.page = 1
  pagination.limit = pageSizeMode.value === 'all' ? ALL_BATCH_SIZE : Number(pageSizeMode.value)
  if (viewMode.value === 'search') return search(true, true)
  return loadRecent(true)
}
const handlePageChange = async () => {
  await requestPage({ mode: viewMode.value })
  resultsRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
const resetSearch = () => {
  clearTimeout(searchTimer)
  filters.keyword = ''
  filters.dateRange = defaultProgressSearchRange()
  pagination.page = 1
  loadRecent(true)
}
const retryLoadAll = () => {
  allLoadError.value = false
  return requestPage({ mode: viewMode.value, append: true })
}

const setupAllLoadObserver = async () => {
  allLoadObserver?.disconnect()
  if (!props.modelValue || pageSizeMode.value !== 'all' || loading.value || appendLoading.value || allLoadError.value || allLoaded.value) return
  await nextTick()
  if (!allLoadSentinel.value || typeof IntersectionObserver === 'undefined') return
  allLoadObserver = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) requestPage({ mode: viewMode.value, append: true })
  }, { rootMargin: '200px 0px', threshold: 0 })
  allLoadObserver.observe(allLoadSentinel.value)
}

const preserveNextOpen = () => {
  preserveOnNextOpen = true
}

watch(() => props.modelValue, (isOpen) => {
  if (!isOpen) {
    allLoadObserver?.disconnect()
    cancelRequest()
    return
  }
  if (preserveOnNextOpen) {
    preserveOnNextOpen = false
    setupAllLoadObserver()
    return
  }
  filters.keyword = ''
  filters.dateRange = defaultProgressSearchRange()
  pageSizeMode.value = 10
  pagination.page = 1
  pagination.limit = 10
  loadRecent(true)
})
watch(
  [pageSizeMode, () => rows.value.length, () => pagination.total, loading, appendLoading, allLoadError],
  setupAllLoadObserver,
  { flush: 'post' },
)

defineExpose({ preserveNextOpen })

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  allLoadObserver?.disconnect()
  requestController?.abort()
})
</script>

<style scoped>
.progress-search-form{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}.progress-search-keyword{flex:1 1 280px}.progress-search-keyword :deep(.el-form-item__content){min-width:220px}.progress-search-range{flex:0 1 auto}.progress-search-page-size{flex:0 0 auto}.progress-search-page-size .el-select{width:150px}.progress-search-actions{margin-right:0}.progress-search-hint{margin:-4px 0 14px;color:var(--el-text-color-secondary);font-size:12px}.progress-search-summary{margin-bottom:10px;color:var(--el-text-color-secondary);font-size:13px}.progress-search-results{min-height:220px;scroll-margin-top:12px}.progress-search-item{padding:14px 16px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-bg-color)}.progress-search-item+.progress-search-item{margin-top:10px}.progress-search-item__header,.progress-search-item__meta,.progress-search-project{display:flex;align-items:center;gap:8px}.progress-search-item__header{justify-content:space-between}.progress-search-project{min-width:0}.progress-search-project span{overflow:hidden;color:var(--el-text-color-secondary);text-overflow:ellipsis;white-space:nowrap}.progress-search-item__content{margin:10px 0;color:var(--el-text-color-primary);line-height:1.65;white-space:pre-wrap;word-break:break-word}.progress-search-item__content mark{padding:0 2px;color:inherit;background:var(--el-color-warning-light-7);border-radius:2px}.progress-search-item__meta{flex-wrap:wrap;color:var(--el-text-color-secondary);font-size:12px}.progress-search-load-more{display:flex;min-height:40px;align-items:center;justify-content:center;margin-top:12px;color:var(--el-text-color-secondary);font-size:13px}.progress-search-pagination{justify-content:flex-end;margin-top:16px}
@media(max-width:768px){.progress-search-form{display:block}.progress-search-form :deep(.el-form-item){display:flex;margin-right:0}.progress-search-form :deep(.el-form-item__content){min-width:0;flex:1}.progress-search-range :deep(.el-date-editor){width:100%}.progress-search-item__header{align-items:flex-start}.progress-search-project{align-items:flex-start;flex-direction:column}.progress-search-item__meta{align-items:flex-start;flex-direction:column}}
</style>

<style>
.annotation-progress-search-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.annotation-progress-search-dialog .el-dialog__header,.annotation-progress-search-dialog .el-dialog__footer{flex:none}.annotation-progress-search-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-progress-search-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);box-shadow:0 -3px 10px rgba(0,0,0,.04)}
</style>
