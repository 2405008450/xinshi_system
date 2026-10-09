<template>
  <el-dropdown trigger="click" placement="bottom-end" :disabled="locked" @command="openExportDialog">
    <el-button :icon="Download" :loading="locked">
      导出 <el-icon class="export-dropdown-caret"><CaretBottom /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item v-for="mode in exportConfig.modes" :key="mode.type" :command="mode.type">{{ mode.label }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
  <DraggableFormDialog
    v-model="visible" :title="activeMode.title" class="project-export-dialog"
    width="min(520px, calc(100vw - 32px))" top="12vh" append-to-body
    :close-on-click-modal="!locked" :close-on-press-escape="!locked" :show-close="!locked"
    @closed="resetForm"
  >
    <AppForm ref="formRef" :model="form" :rules="rules" label-width="110px" @submit.prevent>
      <el-form-item v-if="byClient" :label="clientLabel" prop="clientId">
        <el-select
          v-model="form.clientId" filterable remote clearable :remote-method="loadClients"
          :loading="clientsLoading" :disabled="exporting" placeholder="输入客户名称或编号搜索" style="width: 100%"
        >
          <el-option v-for="client in clients" :key="client.id" :value="client.id" :label="clientOptionLabel(client)" />
        </el-select>
      </el-form-item>
      <template v-else>
        <el-form-item label="时间口径" prop="timeField">
          <el-select v-model="form.timeField" :disabled="exporting" style="width: 100%">
            <el-option v-for="option in exportConfig.timeOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围" prop="dateRange">
          <el-date-picker
            v-model="form.dateRange" :disabled="exporting" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD"
            popper-class="project-export-date-picker"
            range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" unlink-panels style="width: 100%"
          />
        </el-form-item>
      </template>
      <el-alert :title="activeMode.hint" type="info" :closable="false" show-icon />
    </AppForm>
    <template #footer>
      <el-button :disabled="locked" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="locked" @click="handleExport">{{ activeMode.action }}</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretBottom, Download } from '@element-plus/icons-vue'
import { getClientOptions } from '@/api/clients'
import { exportProjectWorkbook } from '@/api/projectExports'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import {
  getProjectExportConfig, buildProjectExportParams, buildClientReconciliationParams,
  buildProjectExportFilename, downloadProjectWorkbook,
} from '@/utils/projectExport'

const props = defineProps({
  module: { type: String, required: true },
  config: { type: Object, default: null },
  buildFilters: { type: Function, required: true },
  sort: { type: String, default: undefined },
})
const exportConfig = computed(() => props.config || getProjectExportConfig(props.module))
const visible = ref(false)
const exporting = ref(false)
const locked = ref(false)
const type = ref('projects')
const formRef = ref(null)
const form = reactive({ timeField: exportConfig.value.defaultTimeField, dateRange: [], clientId: '' })
const activeMode = computed(() => exportConfig.value.modes.find((mode) => mode.type === type.value) || exportConfig.value.modes[0])
const byClient = computed(() => type.value === 'client_reconciliation')
const clientLabel = computed(() => exportConfig.value.clientLabel || '母客户')
const rules = computed(() => byClient.value ? {
  clientId: [{ required: true, message: `请选择一个${clientLabel.value}`, trigger: 'change' }],
} : {
  timeField: [{ required: true, message: '请选择时间口径', trigger: 'change' }],
  dateRange: [{ required: true, type: 'array', len: 2, message: '请选择完整的时间范围', trigger: 'change' }, {
    validator: (_rule, value, callback) => callback(value?.length === 2 && value[0] > value[1] ? new Error('开始日期不能晚于结束日期') : undefined),
    trigger: 'change',
  }],
})
const clients = ref([])
const clientsLoading = ref(false)
let clientSequence = 0
let clientController
let exportController
let disposed = false
const clientOptionLabel = (client) => {
  const name = client.client_short_name || client.client_name || '未命名客户'
  return client.client_code ? `${name}（${client.client_code}）` : name
}
const selectedClient = computed(() => clients.value.find((client) => String(client.id) === String(form.clientId)))
const loadClients = async (keyword = '') => {
  clientController?.abort()
  clientController = new AbortController()
  const current = ++clientSequence
  clientsLoading.value = true
  try {
    const rows = await getClientOptions({ keyword: String(keyword).trim() || undefined, limit: 50 }, { signal: clientController.signal })
    if (current !== clientSequence || disposed) return
    const selected = selectedClient.value
    clients.value = Array.isArray(rows) ? rows : []
    if (selected && !clients.value.some((client) => String(client.id) === String(selected.id))) clients.value.unshift(selected)
  } catch (error) {
    if (current === clientSequence && error?.code !== 'ERR_CANCELED' && !disposed) {
      ElMessage.error(getLocalizedErrorMessage(error, '加载客户选项失败，请重试'))
    }
  } finally {
    if (current === clientSequence) clientsLoading.value = false
  }
}
const resetForm = () => {
  ++clientSequence
  clientController?.abort()
  clientsLoading.value = false
  clients.value = []
  Object.assign(form, { timeField: exportConfig.value.defaultTimeField, dateRange: [], clientId: '' })
  formRef.value?.clearValidate()
}
const openExportDialog = async (nextType) => {
  if (locked.value || !exportConfig.value.modes.some((mode) => mode.type === nextType)) return
  resetForm()
  type.value = nextType
  visible.value = true
  await nextTick()
  if (disposed) return
  formRef.value?.clearValidate()
  if (byClient.value) loadClients()
}
const handleExport = async () => {
  if (!formRef.value || locked.value) return
  // 校验时锁定提交，但保持字段可聚焦；通过校验后才冻结输入。
  locked.value = true
  try {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid || disposed) return
    exporting.value = true
    const params = byClient.value
      ? buildClientReconciliationParams(form.clientId)
      : buildProjectExportParams(props.buildFilters(), form, props.sort)
    exportController = new AbortController()
    const blob = await exportProjectWorkbook(props.module, type.value, params, { signal: exportController.signal })
    if (disposed) return
    const client = selectedClient.value
    const filename = buildProjectExportFilename(exportConfig.value, activeMode.value, form, client?.client_short_name || client?.client_name || client?.client_code)
    downloadProjectWorkbook(blob, filename)
    visible.value = false
    ElMessage.success('导出成功')
  } catch (error) {
    if (disposed || error?.code === 'ERR_CANCELED') return
    exporting.value = false
    await nextTick()
    await formRef.value?.applyServerErrors(error, { date_start: 'dateRange', date_end: 'dateRange', client_id: 'clientId', time_field: 'timeField' })
    ElMessage.error(getLocalizedErrorMessage(error, `${activeMode.value.title}失败`))
  } finally {
    exporting.value = false
    locked.value = false
  }
}
onBeforeUnmount(() => {
  disposed = true
  ++clientSequence
  clientController?.abort()
  exportController?.abort()
})
defineExpose({ openExportDialog })
</script>

<style>
.export-dropdown-caret { margin-left: 6px; font-size: 12px; }
.project-export-dialog { display: flex; flex-direction: column; max-height: 80vh; overflow: hidden; }
.project-export-dialog .el-dialog__header,
.project-export-dialog .el-dialog__footer { flex-shrink: 0; }
.project-export-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.project-export-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); }
@media (max-width: 560px) {
  .project-export-dialog .el-form-item { flex-direction: column; }
  .project-export-dialog .el-form-item__label { justify-content: flex-start; width: auto !important; }
  .project-export-dialog .el-form-item__content { margin-left: 0 !important; width: 100%; }
  /* 窄屏日历居中显示，避免锚点下方空间不足时超出视口。 */
  .project-export-date-picker { position: fixed !important; top: 50% !important; left: 50% !important; transform: translate(-50%, -50%) !important; max-width: calc(100vw - 32px); }
  .project-export-date-picker .el-popper__arrow { display: none; }
  .project-export-date-picker .el-date-range-picker { width: calc(100vw - 32px); }
  .project-export-date-picker .el-picker-panel__body { width: 100%; min-width: 0; max-height: min(450px, calc(100vh - 160px)); overflow-y: auto; }
  .project-export-date-picker .el-date-range-picker__content { float: none; width: 100%; display: block; }
  .project-export-date-picker .el-date-range-picker__content.is-left { border-right: 0; border-bottom: 1px solid var(--el-border-color-lighter); }
}
</style>
