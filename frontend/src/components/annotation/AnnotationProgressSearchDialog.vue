<template>
  <DraggableFormDialog
    v-model="visible"
    title="项目进度检索"
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
      <el-form-item class="progress-search-actions">
        <el-button type="primary" :disabled="!canSearch" @click="search(true, false)">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </AppForm>

    <div class="progress-search-hint">默认检索最近 3 个月，单次时间范围最多 366 天；仅匹配项目进度中填写的正文。</div>
    <div v-if="searched" class="progress-search-summary">共找到 {{ pagination.total }} 条记录</div>

    <div v-loading="loading" class="progress-search-results">
      <template v-if="rows.length">
        <article v-for="row in rows" :key="row.id" class="progress-search-item">
          <div class="progress-search-item__header">
            <div class="progress-search-project">
              <b>{{ row.projectOrderNo }}</b>
              <span>{{ row.projectName || '未命名项目' }}</span>
            </div>
            <el-button type="primary" link @click="$emit('open-context', row)">查看上下文</el-button>
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
      <el-empty v-else-if="searched && !loading" description="当前条件下未找到进度记录" :image-size="80" />
      <el-empty v-else-if="!loading" description="输入关键词后开始检索" :image-size="80" />
    </div>

    <el-pagination
      v-if="pagination.total > pagination.limit"
      v-model:current-page="pagination.page"
      :page-size="pagination.limit"
      :total="pagination.total"
      layout="total, prev, pager, next, jumper"
      class="progress-search-pagination"
      @current-change="search(false, false)"
    />
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as annotationOpsApi from '@/api/annotationOps'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { defaultProgressSearchRange, isProgressSearchRangeValid, splitKeywordMatches } from '@/utils/annotationProgressSearch'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'open-context', 'closed'])
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })

const STATUS_LABELS = {
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果', resource_sourcing: '资源开拓',
  resource_sourcing_cancelled: '取消资源开拓', trial_preparation: '试标准备', trial_in_progress: '试标中', trial_submitted: '试标已提交',
  trial_passed: '试标通过', trial_failed: '试标未通过', trial_partially_passed: '部分试标通过',
  project_in_progress: '项目进行中', sent_to_client: '已发客户', client_feedback: '客户反馈',
  cancelled: '已取消', partially_cancelled: '已部分取消', paused: '暂停', actively_abandoned: '主动放弃',
}
const filters = reactive({ keyword: '', dateRange: defaultProgressSearchRange() })
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const rows = ref([])
const loading = ref(false)
const searched = ref(false)
let searchTimer
let requestController
let requestId = 0

const canSearch = computed(() => Boolean(filters.keyword.trim()) && isProgressSearchRangeValid(filters.dateRange))
const statusLabel = (value) => STATUS_LABELS[value] || value || '-'
const statusType = (value) => ({
  initial_consultation: 'info', consultation_no_result: 'info', resource_sourcing: 'primary',
  resource_sourcing_cancelled: 'danger', trial_preparation: 'warning', trial_in_progress: 'warning', trial_submitted: 'primary',
  trial_passed: 'success', trial_failed: 'danger', trial_partially_passed: 'warning', project_in_progress: 'primary',
  sent_to_client: 'success', client_feedback: 'warning', cancelled: 'danger', partially_cancelled: 'warning',
  paused: 'warning', actively_abandoned: 'danger',
}[value] || 'info')
const highlight = (content) => splitKeywordMatches(content, filters.keyword)

const clearResults = () => {
  requestController?.abort()
  requestId += 1
  rows.value = []
  pagination.total = 0
  searched.value = false
  loading.value = false
}

const search = async (resetPage = true, silent = false) => {
  clearTimeout(searchTimer)
  if (!filters.keyword.trim()) {
    clearResults()
    if (!silent) ElMessage.warning('请输入进度关键词')
    return
  }
  if (!isProgressSearchRangeValid(filters.dateRange)) {
    clearResults()
    if (!silent) ElMessage.warning('请选择不超过 366 天的有效时间范围')
    return
  }
  if (resetPage) pagination.page = 1
  requestController?.abort()
  requestController = new AbortController()
  const current = ++requestId
  loading.value = true
  try {
    const page = await annotationOpsApi.searchStatusHistory({
      keyword: filters.keyword.trim(),
      dateFrom: filters.dateRange[0],
      dateTo: filters.dateRange[1],
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }, { signal: requestController.signal })
    if (current !== requestId) return
    rows.value = Array.isArray(page?.items) ? page.items : []
    pagination.total = page?.total || 0
    searched.value = true
  } catch (error) {
    if (current !== requestId || error?.code === 'ERR_CANCELED') return
    ElMessage.error(error?.detail || '项目进度检索失败，请稍后重试')
  } finally {
    if (current === requestId) loading.value = false
  }
}

const handleKeywordInput = (value) => {
  clearTimeout(searchTimer)
  if (!value?.trim()) return clearResults()
  searchTimer = setTimeout(() => search(true, true), 400)
}
const handleRangeChange = () => {
  if (!filters.keyword.trim()) return
  search(true, true)
}
const resetSearch = () => {
  clearTimeout(searchTimer)
  filters.keyword = ''
  filters.dateRange = defaultProgressSearchRange()
  pagination.page = 1
  clearResults()
}

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  requestController?.abort()
})
</script>

<style scoped>
.progress-search-form{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}.progress-search-keyword{flex:1 1 280px}.progress-search-keyword :deep(.el-form-item__content){min-width:220px}.progress-search-range{flex:0 1 auto}.progress-search-actions{margin-right:0}.progress-search-hint{margin:-4px 0 14px;color:var(--el-text-color-secondary);font-size:12px}.progress-search-summary{margin-bottom:10px;color:var(--el-text-color-secondary);font-size:13px}.progress-search-results{min-height:220px}.progress-search-item{padding:14px 16px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-bg-color)}.progress-search-item+.progress-search-item{margin-top:10px}.progress-search-item__header,.progress-search-item__meta,.progress-search-project{display:flex;align-items:center;gap:8px}.progress-search-item__header{justify-content:space-between}.progress-search-project{min-width:0}.progress-search-project span{overflow:hidden;color:var(--el-text-color-secondary);text-overflow:ellipsis;white-space:nowrap}.progress-search-item__content{margin:10px 0;color:var(--el-text-color-primary);line-height:1.65;white-space:pre-wrap;word-break:break-word}.progress-search-item__content mark{padding:0 2px;color:inherit;background:var(--el-color-warning-light-7);border-radius:2px}.progress-search-item__meta{flex-wrap:wrap;color:var(--el-text-color-secondary);font-size:12px}.progress-search-pagination{justify-content:flex-end;margin-top:16px}
@media(max-width:768px){.progress-search-form{display:block}.progress-search-form :deep(.el-form-item){display:flex;margin-right:0}.progress-search-form :deep(.el-form-item__content){min-width:0;flex:1}.progress-search-range :deep(.el-date-editor){width:100%}.progress-search-item__header{align-items:flex-start}.progress-search-project{align-items:flex-start;flex-direction:column}.progress-search-item__meta{align-items:flex-start;flex-direction:column}}
</style>

<style>
.annotation-progress-search-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.annotation-progress-search-dialog .el-dialog__header,.annotation-progress-search-dialog .el-dialog__footer{flex:none}.annotation-progress-search-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-progress-search-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);box-shadow:0 -3px 10px rgba(0,0,0,.04)}
</style>
