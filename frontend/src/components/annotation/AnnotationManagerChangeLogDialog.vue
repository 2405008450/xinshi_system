<template>
  <div class="annotation-manager-change-log-panel">
    <AppForm :inline="true" class="manager-log-filters">
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="订单号、项目名称、负责人、操作人或原因"
          class="manager-log-keyword"
          @input="handleKeywordInput"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item label="负责人类型">
        <el-select v-model="filters.managerRole" clearable placeholder="全部" class="manager-log-short-filter" @change="search">
          <el-option label="客户经理" value="client_manager" />
          <el-option label="项目经理" value="project_manager" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="manager-log-advanced-popover">
          <div class="manager-log-advanced-content">
          <AdvancedFilterFieldSearch :active="advancedVisible">
      <el-form-item label="变更方式">
        <el-select v-model="filters.changeMode" clearable placeholder="全部" class="manager-log-short-filter" @change="search">
          <el-option label="批量交接" value="direct_transfer" />
          <el-option label="列表直接修改" value="inline_edit" />
          <el-option label="编辑项目" value="project_edit" />
          <el-option label="上级同步" value="inheritance" />
        </el-select>
      </el-form-item>
      <el-form-item label="变更时间">
        <el-date-picker
          v-model="filters.changedRange"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm:ss"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          class="manager-log-date-filter"
          @change="search"
        />
      </el-form-item>
          </AdvancedFilterFieldSearch>
          <div class="manager-log-advanced-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advancedVisible = false">关闭</el-button></div>
          </div>
          <template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
        </el-popover>
      </el-form-item>
    </AppForm>

    <div v-if="currentProject" class="manager-log-project-filter">
      <div><span class="manager-log-project-label">当前项目</span><strong>{{ currentProject.orderNo }}</strong><span>{{ currentProject.projectName || '-' }}</span></div>
      <el-button link type="primary" @click="clearProject">查看全部项目</el-button>
    </div>

    <div v-loading="loading" class="manager-log-results" :aria-busy="loading">
      <el-alert v-if="loadError" :title="loadError" type="warning" :closable="false" show-icon>
        <el-button type="primary" link @click="load">重试加载</el-button>
      </el-alert>
      <template v-else-if="!loading">
        <div v-if="rows.length" class="manager-log-summary">共 {{ pagination.total }} 条变更记录，按时间从新到旧</div>
        <AnnotationManagerChangeTimeline v-if="rows.length" :rows="rows" :project-id="currentProject?.id || ''" @filter-project="filterProject" />
        <el-empty v-else description="暂无符合条件的负责人变更记录" :image-size="80" />
      </template>
    </div>

    <div v-if="!loadError" class="manager-log-pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100, 200]"
        :pager-count="5"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="load"
        @size-change="handlePageSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import AdvancedFilterFieldSearch from '@/components/common/AdvancedFilterFieldSearch.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { getAnnotationManagerChangeLogs } from '@/api/annotationProjects'
import AppForm from '@/components/common/AppForm.vue'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import AnnotationManagerChangeTimeline from './AnnotationManagerChangeTimeline.vue'

const rows = ref([])
const loading = ref(false)
const loadError = ref('')
const currentProject = ref(null)
const filters = reactive({ keyword: '', managerRole: '', changeMode: '', changedRange: [] })
const advancedVisible = ref(false)
const advancedCount = computed(() => Number(Boolean(filters.changeMode)) + Number(Boolean(filters.changedRange?.length)))
const clearAdvanced = () => { filters.changeMode = ''; filters.changedRange = []; search() }
const pagination = reactive({ page: 1, pageSize: 50, total: 0 })
let debounceTimer
let requestController
let requestSequence = 0

const buildParams = () => ({
  project_id: currentProject.value?.id || undefined,
  keyword: filters.keyword.trim() || undefined,
  manager_role: filters.managerRole || undefined,
  change_mode: filters.changeMode || undefined,
  changed_from: filters.changedRange?.[0] ? filters.changedRange[0] + '+08:00' : undefined,
  changed_to: filters.changedRange?.[1] ? filters.changedRange[1] + '+08:00' : undefined,
  skip: (pagination.page - 1) * pagination.pageSize,
  limit: pagination.pageSize,
})
const cancelRequest = () => requestController?.abort()
const load = async () => {
  cancelRequest()
  requestController = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  rows.value = []
  loadError.value = ''
  try {
    const result = await getAnnotationManagerChangeLogs(buildParams(), { signal: requestController.signal })
    if (sequence !== requestSequence) return
    rows.value = result.items || []
    pagination.total = result.total || 0
  } catch (error) {
    if (sequence === requestSequence && error?.code !== 'ERR_CANCELED') loadError.value = getLocalizedErrorMessage(error, '加载负责人变更记录失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
const search = () => { clearTimeout(debounceTimer); pagination.page = 1; load() }
const handleKeywordInput = value => {
  clearTimeout(debounceTimer)
  if (!String(value || '').trim()) return search()
  debounceTimer = window.setTimeout(search, 400)
}
const reset = () => {
  currentProject.value = null
  Object.assign(filters, { keyword: '', managerRole: '', changeMode: '', changedRange: [] })
  search()
}
const filterProject = row => {
  currentProject.value = { id: row.projectId, orderNo: row.orderNo, projectName: row.projectName }
  search()
}
const clearProject = () => { currentProject.value = null; search() }
const handlePageSizeChange = () => { pagination.page = 1; load() }

defineExpose({ load })

onBeforeUnmount(() => { clearTimeout(debounceTimer); cancelRequest() })
</script>

<style>
.annotation-manager-change-log-panel{min-width:0;padding-top:4px}
.manager-log-filters{display:flex;align-items:flex-end;gap:0;flex-wrap:wrap}
.manager-log-keyword{width:270px}.manager-log-short-filter{width:140px}.manager-log-date-filter{width:340px}
.manager-log-pagination{display:flex;justify-content:flex-end;margin-top:16px}
.manager-log-pagination .el-pagination{max-width:100%;flex-wrap:wrap;row-gap:8px}
.manager-log-results{min-height:180px}
.manager-log-summary{margin:0 0 16px;color:var(--el-text-color-secondary);font-size:12px}
.manager-log-project-filter{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:10px 12px;margin:0 0 18px;border:1px solid var(--el-border-color-light);border-radius:6px;background:var(--el-fill-color-lighter)}
.manager-log-project-filter>div{display:flex;gap:4px 12px;flex-wrap:wrap;min-width:0;line-height:1.6;overflow-wrap:anywhere}
.manager-log-project-filter>.el-button{flex:none}
.manager-log-project-label{color:var(--el-text-color-secondary)}
.manager-log-advanced-popover{max-width:calc(100vw - 32px);box-sizing:border-box}
.manager-log-advanced-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}
.manager-log-advanced-actions{display:flex;justify-content:flex-end;gap:8px}
@media(max-width:768px){.manager-log-keyword,.manager-log-short-filter,.manager-log-date-filter{width:100%}.manager-log-filters>.el-form-item{width:100%;margin-right:0}.manager-log-filters>.el-form-item>.el-form-item__content{min-width:0;flex:1}.manager-log-project-filter{flex-direction:column;gap:4px}}
</style>
