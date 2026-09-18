<template>
  <DraggableFormDialog
    :model-value="modelValue"
    title="标注项目负责人变更记录"
    width="min(1180px, calc(100vw - 32px))"
    top="5vh"
    class="annotation-manager-change-log-dialog"
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
    @closed="cancelRequest"
  >
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
      <el-form-item label="变更方式">
        <el-select v-model="filters.changeMode" clearable placeholder="全部" class="manager-log-short-filter" @change="search">
          <el-option label="批量交接" value="direct_transfer" />
          <el-option label="列表直接修改" value="inline_edit" />
          <el-option label="编辑项目" value="project_edit" />
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
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </AppForm>

    <el-table v-loading="loading" :data="rows" border row-key="id" class="manager-log-table">
      <el-table-column type="index" label="序号" width="64" :index="indexMethod" />
      <el-table-column label="变更时间" width="155"><template #default="{ row }">{{ formatDateTime(row.changedAt) }}</template></el-table-column>
      <el-table-column prop="orderNo" label="订单号" min-width="145" show-overflow-tooltip />
      <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="类型" width="95"><template #default="{ row }">{{ roleLabel(row.managerRole) }}</template></el-table-column>
      <el-table-column label="原负责人" min-width="105"><template #default="{ row }">{{ row.previousManagerName || '未分配' }}</template></el-table-column>
      <el-table-column label="新负责人" min-width="105"><template #default="{ row }">{{ row.newManagerName || '未分配' }}</template></el-table-column>
      <el-table-column label="变更方式" width="120"><template #default="{ row }"><el-tag size="small" effect="plain">{{ modeLabel(row.changeMode) }}</el-tag></template></el-table-column>
      <el-table-column label="操作人" min-width="105"><template #default="{ row }">{{ row.actorNameSnapshot || row.actorUsernameSnapshot || '系统' }}</template></el-table-column>
      <el-table-column prop="reason" label="原因/说明" min-width="190" show-overflow-tooltip><template #default="{ row }">{{ row.reason || '-' }}</template></el-table-column>
    </el-table>

    <div class="manager-log-pagination">
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
    <template #footer><el-button @click="emit('update:modelValue', false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAnnotationManagerChangeLogs } from '@/api/annotationProjects'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])
const rows = ref([])
const loading = ref(false)
const filters = reactive({ keyword: '', managerRole: '', changeMode: '', changedRange: [] })
const pagination = reactive({ page: 1, pageSize: 50, total: 0 })
let debounceTimer
let requestController
let requestSequence = 0

const roleLabel = value => ({ client_manager: '客户经理', project_manager: '项目经理' }[value] || value || '-')
const modeLabel = value => ({ direct_transfer: '批量交接', inline_edit: '列表直接修改', project_edit: '编辑项目' }[value] || value || '-')
const indexMethod = index => (pagination.page - 1) * pagination.pageSize + index + 1
const buildParams = () => ({
  keyword: filters.keyword.trim() || undefined,
  manager_role: filters.managerRole || undefined,
  change_mode: filters.changeMode || undefined,
  changed_from: filters.changedRange?.[0] || undefined,
  changed_to: filters.changedRange?.[1] || undefined,
  skip: (pagination.page - 1) * pagination.pageSize,
  limit: pagination.pageSize,
})
const cancelRequest = () => requestController?.abort()
const load = async () => {
  cancelRequest()
  requestController = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const result = await getAnnotationManagerChangeLogs(buildParams(), { signal: requestController.signal })
    if (sequence !== requestSequence) return
    rows.value = result.items || []
    pagination.total = result.total || 0
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED') ElMessage.error(error?.detail || '加载负责人变更记录失败')
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
  Object.assign(filters, { keyword: '', managerRole: '', changeMode: '', changedRange: [] })
  search()
}
const handlePageSizeChange = () => { pagination.page = 1; load() }

onBeforeUnmount(() => { clearTimeout(debounceTimer); cancelRequest() })
</script>

<style>
.annotation-manager-change-log-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}
.annotation-manager-change-log-dialog .el-dialog__header,.annotation-manager-change-log-dialog .el-dialog__footer{flex:0 0 auto}
.annotation-manager-change-log-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.annotation-manager-change-log-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}
.manager-log-filters{display:flex;align-items:flex-end;gap:0;flex-wrap:wrap}
.manager-log-keyword{width:270px}.manager-log-short-filter{width:140px}.manager-log-date-filter{width:340px}
.manager-log-pagination{display:flex;justify-content:flex-end;margin-top:16px}
@media(max-width:768px){.manager-log-keyword,.manager-log-short-filter,.manager-log-date-filter{width:100%}}
</style>
