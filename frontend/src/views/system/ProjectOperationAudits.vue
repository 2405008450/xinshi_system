<template>
  <el-card class="audit-card">
    <template #header>
      <div class="page-header">
        <div>
          <h2>项目操作审计</h2>
          <p>永久保留四类项目的新增、删除和订单号修改记录，用于追溯订单号及操作人。</p>
        </div>
      </div>
    </template>

    <div class="filter-bar">
      <el-input
        v-model="filters.keyword"
        clearable
        placeholder="订单号或项目名称"
        class="keyword-input"
        @input="handleKeywordInput"
        @keyup.enter="search"
      />
      <el-select v-model="filters.projectType" clearable placeholder="项目类型" class="short-filter" @change="search">
        <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="filters.operationType" clearable placeholder="操作类型" class="short-filter" @change="search">
        <el-option label="新增" value="create" />
        <el-option label="删除" value="delete" />
        <el-option label="修改订单号" value="order_no_change" />
      </el-select>
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <AdvancedFilterPopover
        v-model:visible="advancedVisible"
        :count="advancedCount"
        @clear="clearAdvancedFilters"
        @reset="resetFilters"
      >
        <div class="advanced-content">
          <AppForm label-width="84px">
            <el-form-item label="操作人">
              <el-input
                v-model="filters.operatorKeyword"
                clearable
                placeholder="姓名或用户名"
                @input="handleAdvancedTextInput"
                @keyup.enter="search"
              />
            </el-form-item>
            <el-form-item label="操作时间">
              <el-date-picker
                v-model="filters.occurredRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
                value-format="YYYY-MM-DDTHH:mm:ss"
                style="width: 100%"
                @change="search"
              />
            </el-form-item>
          </AppForm>
        </div>
      </AdvancedFilterPopover>
    </div>

    <el-table v-loading="loading" :data="rows" border row-key="id">
      <el-table-column type="index" label="序号" width="70" :index="indexMethod" />
      <el-table-column prop="occurred_at" label="操作时间" min-width="165">
        <template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template>
      </el-table-column>
      <el-table-column prop="order_no" label="订单号" min-width="165" />
      <el-table-column prop="project_type" label="项目类型" width="105">
        <template #default="{ row }">{{ projectTypeLabel(row.project_type) }}</template>
      </el-table-column>
      <el-table-column prop="operation_type" label="操作" width="120">
        <template #default="{ row }">
          <el-tag :type="operationTagType(row.operation_type)">{{ operationLabel(row.operation_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="project_name" label="项目名称" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ row.project_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作人" min-width="140">
        <template #default="{ row }">{{ actorLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="来源" min-width="135">
        <template #default="{ row }">{{ sourceLabel(row.operation_source) }}</template>
      </el-table-column>
      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <el-popover trigger="click" placement="left" :width="760">
            <template #reference><el-button link type="primary">查看详情</el-button></template>
            <div class="audit-detail">
              <h3>{{ row.order_no }} 操作详情</h3>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="订单号">{{ row.order_no }}</el-descriptions-item>
                <el-descriptions-item label="项目类型">{{ projectTypeLabel(row.project_type) }}</el-descriptions-item>
                <el-descriptions-item label="操作类型">{{ operationLabel(row.operation_type) }}</el-descriptions-item>
                <el-descriptions-item label="操作时间">{{ formatDateTime(row.occurred_at) }}</el-descriptions-item>
                <el-descriptions-item label="操作人">{{ actorLabel(row) }}</el-descriptions-item>
                <el-descriptions-item label="操作来源">{{ sourceLabel(row.operation_source) }}</el-descriptions-item>
                <el-descriptions-item label="项目名称" :span="2">{{ row.project_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="项目原始 ID" :span="2">{{ row.project_id }}</el-descriptions-item>
                <el-descriptions-item v-if="row.operation_type === 'order_no_change'" label="原订单号">{{ row.previous_order_no || '-' }}</el-descriptions-item>
                <el-descriptions-item v-if="row.operation_type === 'order_no_change'" label="新订单号">{{ row.order_no }}</el-descriptions-item>
                <el-descriptions-item v-if="row.operation_type === 'order_no_change'" label="修改原因" :span="2">{{ row.change_reason || '-' }}</el-descriptions-item>
              </el-descriptions>
              <h4>项目数据快照</h4>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item
                  v-for="item in snapshotItems(row.project_snapshot)"
                  :key="item.key"
                  :label="item.label"
                  :span="item.span"
                >{{ item.value }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="load"
        @size-change="handlePageSizeChange"
      />
    </div>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjectOperationAudits } from '@/api/projectAudits'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const projectTypeOptions = [
  { value: 'translation', label: '笔译' },
  { value: 'interpretation', label: '口译' },
  { value: 'annotation', label: '标注' },
  { value: 'recruitment', label: '招聘' },
]
const sourceLabels = {
  project_form: '项目表单',
  project_delete: '删除管理',
  consultation_confirmation: '咨询确认建项',
  legacy_import: '历史导入',
  project_order_no_change: '订单号修改',
}
const fieldLabels = {
  id: '项目 ID', order_no: '订单号', project_name: '项目名称', project_status: '项目状态',
  consultation_id: '咨询 ID', client_id: '客户 ID', sub_client_id: '子客户 ID',
  customer_order_no: '客户单号', email_subject_preview: '邮件主题预览', created_by: '创建人 ID',
  created_at: '创建时间', updated_at: '更新时间', remarks: '备注', task_type: '任务类型',
}

const loading = ref(false)
const rows = ref([])
const advancedVisible = ref(false)
const filters = reactive({ keyword: '', projectType: '', operationType: '', operatorKeyword: '', occurredRange: [] })
const pagination = reactive({ page: 1, pageSize: 50, total: 0 })
const advancedCount = computed(() => Number(Boolean(filters.operatorKeyword.trim())) + Number(Boolean(filters.occurredRange?.length)))
let debounceTimer
let requestController
let requestSequence = 0

const projectTypeLabel = value => projectTypeOptions.find(item => item.value === value)?.label || value || '-'
const operationLabel = value => ({create:'新增',delete:'删除',order_no_change:'修改订单号'}[value] || value || '-')
const operationTagType = value => ({create:'success',delete:'danger',order_no_change:'warning'}[value] || 'info')
const sourceLabel = value => sourceLabels[value] || value || '-'
const actorLabel = row => row.actor_name_snapshot || row.actor_username_snapshot || '未知用户'
const indexMethod = index => (pagination.page - 1) * pagination.pageSize + index + 1
const snapshotValue = value => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
const snapshotItems = snapshot => Object.entries(snapshot || {}).map(([key, value]) => ({
  key,
  label: fieldLabels[key] || key,
  value: snapshotValue(value),
  span: typeof value === 'object' || String(value || '').length > 80 ? 2 : 1,
}))

const buildParams = () => ({
  keyword: filters.keyword.trim() || undefined,
  project_type: filters.projectType || undefined,
  operation_type: filters.operationType || undefined,
  operator_keyword: filters.operatorKeyword.trim() || undefined,
  occurred_from: filters.occurredRange?.[0] || undefined,
  occurred_to: filters.occurredRange?.[1] || undefined,
  skip: (pagination.page - 1) * pagination.pageSize,
  limit: pagination.pageSize,
})

const load = async () => {
  requestController?.abort()
  requestController = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const result = await getProjectOperationAudits(buildParams(), requestController.signal)
    if (sequence !== requestSequence) return
    rows.value = result.items || []
    pagination.total = result.total || 0
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED') ElMessage.error(error?.detail || '加载项目操作审计失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
const search = () => { clearTimeout(debounceTimer); pagination.page = 1; load() }
const scheduleSearch = value => {
  clearTimeout(debounceTimer)
  if (!value) return search()
  debounceTimer = window.setTimeout(search, 400)
}
const handleKeywordInput = value => scheduleSearch(String(value || '').trim())
const handleAdvancedTextInput = value => scheduleSearch(String(value || '').trim())
const clearAdvancedFilters = () => { filters.operatorKeyword = ''; filters.occurredRange = []; search() }
const resetFilters = () => {
  Object.assign(filters, { keyword: '', projectType: '', operationType: '', operatorKeyword: '', occurredRange: [] })
  search()
}
const handlePageSizeChange = () => { pagination.page = 1; load() }

onMounted(load)
onBeforeUnmount(() => { clearTimeout(debounceTimer); requestController?.abort() })
</script>

<style scoped>
.audit-card{min-width:0}.page-header{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-header h2{margin:0}.page-header p{margin:6px 0 0;color:var(--el-text-color-secondary)}.filter-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px}.keyword-input{width:280px}.short-filter{width:150px}.advanced-content{padding-right:4px}.pagination-row{display:flex;justify-content:flex-end;margin-top:16px}.audit-detail{max-height:560px;overflow-y:auto}.audit-detail h3{margin:0 0 12px}.audit-detail h4{margin:16px 0 10px}.audit-detail :deep(.el-descriptions__content){white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:768px){.keyword-input,.short-filter{width:100%}}
</style>
