<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    destroy-on-close
    class="annotation-manager-transfer-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="resetDialog"
    @open="loadOptions"
  >
    <el-alert
      :title="alertTitle"
      type="warning"
      :closable="false"
      show-icon
    />

    <AppForm
      ref="formRef"
      :model="form"
      :rules="rules"
      :validate-on-rule-change="false"
      label-width="105px"
      class="manager-transfer-form"
    >
      <el-form-item label="交接类型">
        <el-radio-group v-model="selectedManagerType" :disabled="submitting" @change="handleManagerTypeChange">
          <el-radio-button label="project_manager">项目经理</el-radio-button>
          <el-radio-button label="client_manager">客户经理</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <el-form-item :label="sourceLabel" prop="sourceManagerId">
            <el-select
              v-model="form.sourceManagerId"
              filterable
              :placeholder="`请选择${sourceLabel}`"
              style="width: 100%"
              :loading="optionsLoading"
              @change="handleSourceChange"
            >
              <el-option
                v-for="manager in sourceManagers"
                :key="manager.id"
                :value="manager.id"
                :label="sourceManagerLabel(manager)"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-form-item :label="targetLabel" prop="targetManagerId">
            <el-select
              v-model="form.targetManagerId"
              filterable
              :placeholder="`请选择${targetLabel}`"
              style="width: 100%"
              :loading="optionsLoading"
            >
              <el-option
                v-for="manager in availableTargetManagers"
                :key="manager.id"
                :value="manager.id"
                :label="targetManagerLabel(manager)"
                :disabled="manager.is_on_leave"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="交接原因" prop="reason">
        <el-input
          v-model="form.reason"
          type="textarea"
          :rows="3"
          maxlength="500"
          show-word-limit
          placeholder="请说明离职、岗位调整等交接原因"
        />
      </el-form-item>
    </AppForm>

    <div class="manager-transfer-preview">
      <div class="manager-transfer-preview__header">
        <div>
          <strong>活跃标注项目预览</strong>
          <span class="manager-transfer-preview__hint">服务端加载全部项目，不受当前列表分页影响</span>
        </div>
        <div class="manager-transfer-preview__actions">
          <span>共 {{ previewProjects.length }} 个，已选择 {{ selectedProjects.length }} 个</span>
          <el-button
            link
            type="primary"
            :disabled="!previewProjects.length"
            @click="selectAllProjects"
          >
            重新全选
          </el-button>
        </div>
      </div>
      <div v-if="statusEntries.length" class="manager-transfer-statuses">
        <el-tag v-for="item in statusEntries" :key="item.status" size="small" effect="plain">
          {{ statusLabel(item.status) }} {{ item.count }}
        </el-tag>
      </div>
      <el-table
        ref="previewTableRef"
        v-loading="previewLoading"
        :data="previewProjects"
        row-key="project_id"
        border
        size="small"
        height="320"
        @selection-change="selectedProjects = $event"
      >
        <template #empty>
          <span>{{ form.sourceManagerId ? `该${managerLabel}暂无可交接的活跃标注项目` : `请先选择${sourceLabel}` }}</span>
        </template>
        <el-table-column type="selection" width="48" />
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="order_no" label="订单号" width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目名称" min-width="210" show-overflow-tooltip />
        <el-table-column prop="client_short_name" label="客户简称" width="130" show-overflow-tooltip />
        <el-table-column label="项目状态" width="130">
          <template #default="{ row }">{{ statusLabel(row.project_status) }}</template>
        </el-table-column>
        <el-table-column prop="language_pair" label="语言方向" min-width="140" show-overflow-tooltip />
      </el-table>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="danger"
        :loading="submitting"
        :disabled="!selectedProjects.length"
        @click="submitTransfer"
      >
        确认直接移交（{{ selectedProjects.length }}）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  directTransferAnnotationClientManagerAPI,
  directTransferAnnotationManagerAPI,
  getAnnotationClientManagerTransferOptionsAPI,
  getAnnotationManagerTransferOptionsAPI,
  previewAnnotationClientManagerTransferAPI,
  previewAnnotationManagerTransferAPI,
} from '@/api/workflow'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { getProjectStatusLabel } from '@/utils/projectStatus'

defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'transferred'])
const formRef = ref(null)
const previewTableRef = ref(null)
const optionsLoading = ref(false)
const previewLoading = ref(false)
const submitting = ref(false)
const sourceManagers = ref([])
const targetManagers = ref([])
const previewProjects = ref([])
const selectedProjects = ref([])
const statusCounts = ref({})
const selectedManagerType = ref('project_manager')
let optionsRequestId = 0
let previewRequestId = 0
const form = reactive({ sourceManagerId: '', targetManagerId: '', reason: '' })
const isClientManagerTransfer = computed(() => selectedManagerType.value === 'client_manager')
const managerLabel = computed(() => isClientManagerTransfer.value ? '客户经理' : '项目经理')
const sourceLabel = computed(() => `原${managerLabel.value}`)
const targetLabel = computed(() => `新${managerLabel.value}`)
const dialogTitle = computed(() => `${managerLabel.value}离职交接`)
const alertTitle = computed(() => (
  `该操作由超级管理员直接生效，无需接收人确认；只会变更${managerLabel.value}，不会修改客户及其他项目角色。`
))
const rules = computed(() => ({
  sourceManagerId: [{ required: true, message: `请选择${sourceLabel.value}`, trigger: 'change' }],
  targetManagerId: [{ required: true, message: `请选择${targetLabel.value}`, trigger: 'change' }],
  reason: [{
    validator: (_rule, value, callback) => String(value || '').trim()
      ? callback()
      : callback(new Error('请填写交接原因')),
    trigger: ['blur', 'change'],
  }],
}))

const availableTargetManagers = computed(() => (
  targetManagers.value.filter(manager => String(manager.id) !== String(form.sourceManagerId))
))
const statusEntries = computed(() => Object.entries(statusCounts.value).map(([status, count]) => ({ status, count })))
const statusLabel = status => getProjectStatusLabel('annotation', status)
const managerName = manager => manager.full_name || manager.username
const sourceManagerLabel = manager => `${managerName(manager)}${manager.is_active ? '' : '（已停用）'} · ${manager.project_count} 个活跃项目`
const targetManagerLabel = manager => manager.is_on_leave
  ? `${managerName(manager)}（${manager.assignment_disabled_reason || '正在请假'}）`
  : managerName(manager)

async function loadOptions() {
  const currentRequestId = ++optionsRequestId
  const managerType = selectedManagerType.value
  optionsLoading.value = true
  try {
    const response = await (
      managerType === 'client_manager'
        ? getAnnotationClientManagerTransferOptionsAPI()
        : getAnnotationManagerTransferOptionsAPI()
    )
    if (currentRequestId !== optionsRequestId || managerType !== selectedManagerType.value) return
    sourceManagers.value = Array.isArray(response?.source_managers) ? response.source_managers : []
    targetManagers.value = Array.isArray(response?.target_managers) ? response.target_managers : []
  } catch (error) {
    if (currentRequestId !== optionsRequestId) return
    ElMessage.error(getLocalizedErrorMessage(error, '加载交接人员失败'))
  } finally {
    if (currentRequestId === optionsRequestId) optionsLoading.value = false
  }
}

async function handleManagerTypeChange() {
  previewRequestId += 1
  Object.assign(form, { sourceManagerId: '', targetManagerId: '', reason: '' })
  sourceManagers.value = []
  targetManagers.value = []
  previewProjects.value = []
  selectedProjects.value = []
  statusCounts.value = {}
  previewLoading.value = false
  await nextTick()
  formRef.value?.clearValidate()
  loadOptions()
}

async function handleSourceChange() {
  const currentRequestId = ++previewRequestId
  const sourceManagerId = form.sourceManagerId
  if (String(form.targetManagerId) === String(form.sourceManagerId)) form.targetManagerId = ''
  previewProjects.value = []
  selectedProjects.value = []
  statusCounts.value = {}
  if (!sourceManagerId) return
  previewLoading.value = true
  try {
    const response = await (
      isClientManagerTransfer.value
        ? previewAnnotationClientManagerTransferAPI(sourceManagerId)
        : previewAnnotationManagerTransferAPI(sourceManagerId)
    )
    if (currentRequestId !== previewRequestId || String(form.sourceManagerId) !== String(sourceManagerId)) return
    previewProjects.value = Array.isArray(response?.projects) ? response.projects : []
    statusCounts.value = response?.status_counts || {}
    await nextTick()
    selectAllProjects()
  } catch (error) {
    if (currentRequestId !== previewRequestId) return
    ElMessage.error(getLocalizedErrorMessage(error, '加载待交接项目失败'))
  } finally {
    if (currentRequestId === previewRequestId) previewLoading.value = false
  }
}

function selectAllProjects() {
  previewTableRef.value?.clearSelection()
  previewProjects.value.forEach(row => previewTableRef.value?.toggleRowSelection(row, true))
}

async function submitTransfer() {
  if (!selectedProjects.value.length) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    const { value } = await ElMessageBox.prompt(
      `将立即把所选 ${selectedProjects.value.length} 个项目改绑给${targetLabel.value}，且无需对方确认。请输入“交接”继续。`,
      '确认离职交接',
      {
        type: 'warning',
        confirmButtonText: '确认移交',
        cancelButtonText: '取消',
        inputPlaceholder: '请输入：交接',
        inputValidator: value => String(value || '').trim() === '交接' || '请输入“交接”',
      },
    )
    if (String(value || '').trim() !== '交接') return
    submitting.value = true
    const transferAPI = isClientManagerTransfer.value
      ? directTransferAnnotationClientManagerAPI
      : directTransferAnnotationManagerAPI
    await transferAPI({
      source_manager_id: form.sourceManagerId,
      target_manager_id: form.targetManagerId,
      project_ids: selectedProjects.value.map(item => item.project_id),
      reason: form.reason.trim(),
    })
    ElMessage.success(`已完成 ${selectedProjects.value.length} 个标注项目的${managerLabel.value}移交`)
    emit('update:modelValue', false)
    emit('transferred')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getLocalizedErrorMessage(error, `${managerLabel.value}移交失败`))
    }
  } finally {
    submitting.value = false
  }
}

function resetDialog() {
  optionsRequestId += 1
  previewRequestId += 1
  selectedManagerType.value = 'project_manager'
  Object.assign(form, { sourceManagerId: '', targetManagerId: '', reason: '' })
  sourceManagers.value = []
  targetManagers.value = []
  previewProjects.value = []
  selectedProjects.value = []
  statusCounts.value = {}
  optionsLoading.value = false
  previewLoading.value = false
  formRef.value?.clearValidate()
}
</script>

<style>
.annotation-manager-transfer-dialog {
  display: flex;
  max-height: 90vh;
  flex-direction: column;
  overflow: hidden;
}
.annotation-manager-transfer-dialog .el-dialog__header,
.annotation-manager-transfer-dialog .el-dialog__footer {
  flex: 0 0 auto;
}
.annotation-manager-transfer-dialog .el-dialog__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.annotation-manager-transfer-dialog .el-dialog__footer {
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
  box-shadow: 0 -3px 10px rgba(0, 0, 0, 0.04);
}
.manager-transfer-form {
  margin-top: 18px;
}
.manager-transfer-preview__header,
.manager-transfer-preview__actions,
.manager-transfer-statuses {
  display: flex;
  align-items: center;
}
.manager-transfer-preview__header {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}
.manager-transfer-preview__hint {
  margin-left: 10px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.manager-transfer-preview__actions,
.manager-transfer-statuses {
  gap: 8px;
}
.manager-transfer-preview__actions {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.manager-transfer-statuses {
  flex-wrap: wrap;
  margin-bottom: 10px;
}
@media (max-width: 768px) {
  .manager-transfer-preview__header {
    align-items: flex-start;
    flex-direction: column;
  }
  .manager-transfer-preview__hint {
    display: block;
    margin: 4px 0 0;
  }
}
</style>
