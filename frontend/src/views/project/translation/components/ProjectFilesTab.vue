<template>
  <div class="path-group-panel">
    <el-empty v-if="!projectId && !allowDraft" description="请先选择项目" />
    <template v-else>
    <div class="files-header">
      <div>
        <strong>关联订单：{{ associatedOrderNo || '保存项目后自动生成' }}</strong>
        <div class="files-description">
          每个项目固定维护一组文件分类和流程路径，无需新增文件条目。
        </div>
      </div>
    </div>

    <el-alert
      v-if="entityType === 'suborder'"
      type="info"
      :closable="false"
      class="files-hint"
      title="当前查看的是子订单，路径组归属于所属母订单。"
    />
    <el-alert
      v-else-if="!projectId"
      type="info"
      :closable="false"
      class="files-hint"
      title="可直接填写路径组，保存项目时会自动关联到新订单。"
    />

    <el-form
      ref="pathGroupFormRef"
      v-loading="fileLoading"
      :model="pathGroupForm"
      :rules="pathGroupRules"
      :disabled="!canWrite"
      label-width="130px"
      class="path-group-form"
    >
      <el-collapse v-model="expandedSections" class="file-edit-collapse">
        <el-collapse-item name="classification">
          <template #title>
            <div class="file-edit-collapse__title">
              <span>文件分类</span>
              <span class="file-edit-collapse__hint">领域、类型、格式、属性和难度</span>
            </div>
          </template>
          <div class="file-edit-collapse__body">
            <el-row :gutter="16">
              <el-col :xs="24" :md="12">
                <el-form-item label="翻译文本领域一级">
                  <el-input v-model="pathGroupForm.translation_domain_level1" clearable placeholder="请输入一级领域" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="翻译文本领域二级">
                  <el-input
                    v-model="pathGroupForm.translation_domain_level2"
                    clearable
                    :disabled="!canWrite || !pathGroupForm.translation_domain_level1"
                    placeholder="请输入二级领域"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="文件类型一级">
                  <el-input v-model="pathGroupForm.file_type" clearable placeholder="请输入一级类型" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="文件类型二级">
                  <el-input
                    v-model="pathGroupForm.file_type_secondary"
                    clearable
                    :disabled="!canWrite || !pathGroupForm.file_type"
                    placeholder="请输入二级类型"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="文件格式">
                  <el-input v-model="pathGroupForm.file_format" clearable placeholder="如 DOCX、PDF、XLSX" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="文件难度">
                  <el-input v-model="pathGroupForm.file_difficulty" clearable placeholder="请输入文件难度" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-form-item label="文件属性一级">
                  <el-input v-model="pathGroupForm.file_attribute_level1" clearable placeholder="一级属性" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-form-item label="文件属性二级">
                  <el-input
                    v-model="pathGroupForm.file_attribute_level2"
                    clearable
                    :disabled="!canWrite || !pathGroupForm.file_attribute_level1"
                    placeholder="二级属性"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-form-item label="文件属性三级">
                  <el-input
                    v-model="pathGroupForm.file_attribute_level3"
                    clearable
                    :disabled="!canWrite || !pathGroupForm.file_attribute_level2"
                    placeholder="三级属性"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </el-collapse-item>

        <el-collapse-item name="paths">
          <template #title>
            <div class="file-edit-collapse__title">
              <span>文件路径</span>
              <span class="file-edit-collapse__hint">填写任一信息后原文路径必填，其他路径按流程补充</span>
            </div>
          </template>
          <div class="file-edit-collapse__body">
            <el-form-item label="原文路径" prop="storage_path">
              <el-input v-model="pathGroupForm.storage_path" placeholder="如 \\win-server\原文" />
            </el-form-item>
            <el-form-item label="派稿文路径">
              <el-input v-model="pathGroupForm.dispatch_path" placeholder="如 \\win-server\派稿" />
            </el-form-item>
            <el-form-item v-if="referenceFilePathOne !== undefined" label="参考文件路径一">
              <el-input
                :model-value="referenceFilePathOne"
                type="textarea"
                :rows="2"
                placeholder="供稿件安排发信时引用，通过项目外键自动带入"
                @update:model-value="emit('update:referenceFilePathOne', $event)"
              />
            </el-form-item>
            <el-form-item label="译文路径">
              <el-input v-model="pathGroupForm.translation_path" placeholder="如 \\win-server\译文" />
            </el-form-item>
            <el-form-item label="译员发回路径">
              <el-input v-model="pathGroupForm.translator_return_path" placeholder="填写后项目状态自动变为“译员发回”" />
            </el-form-item>
            <el-form-item label="发客户路径">
              <el-input v-model="pathGroupForm.client_delivery_path" placeholder="填写后项目状态自动变为“已发客户”" />
            </el-form-item>
            <el-form-item label="项目反馈路径">
              <el-input v-model="pathGroupForm.project_feedback_path" placeholder="填写后项目状态自动变为“客户反馈”" />
            </el-form-item>
            <el-form-item label="反馈后发客户路径">
              <el-input v-model="pathGroupForm.feedback_delivery_path" placeholder="填写后项目状态自动变为“反馈后发客户”" />
            </el-form-item>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-form>

    <div v-if="canWrite && showSaveAction && projectId" class="path-group-actions">
      <el-button
        v-if="pathGroupForm.id"
        type="danger"
        plain
        :disabled="fileSaving"
        @click="handlePathGroupDelete"
      >
        清空路径组
      </el-button>
      <el-button type="primary" :loading="fileSaving" @click="savePathGroup()">
        保存路径组
      </el-button>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createProjectFile, deleteProjectFile, getProjectFilesByProject, updateProjectFile } from '@/api/projectFiles'
import { hasPermission } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const emit = defineEmits(['status-change', 'update:referenceFilePathOne'])
const props = defineProps({
  projectId: {
    type: [String, Number],
    default: ''
  },
  orderNo: {
    type: String,
    default: ''
  },
  entityType: {
    type: String,
    default: 'project'
  },
  active: {
    type: Boolean,
    default: false
  },
  showSaveAction: {
    type: Boolean,
    default: true
  },
  allowDraft: {
    type: Boolean,
    default: false
  },
  referenceFilePathOne: {
    type: String,
    default: undefined
  }
})

const createEmptyPathGroup = () => ({
  id: null,
  file_name: '',
  storage_path: '',
  dispatch_path: '',
  translation_path: '',
  translator_return_path: '',
  client_delivery_path: '',
  project_feedback_path: '',
  feedback_delivery_path: '',
  translation_domain_level1: '',
  translation_domain_level2: '',
  file_type: '',
  file_type_secondary: '',
  file_format: '',
  file_attribute_level1: '',
  file_attribute_level2: '',
  file_attribute_level3: '',
  file_difficulty: ''
})
const pathGroupDataKeys = Object.keys(createEmptyPathGroup()).filter((key) => !['id', 'file_name'].includes(key))
const canWrite = computed(() => hasPermission('project_files:write'))
const associatedOrderNo = computed(() => props.orderNo || '')
const fileLoading = ref(false)
const fileSaving = ref(false)
const pathGroupFormRef = ref(null)
const expandedSections = ref(['classification', 'paths'])
const pathGroupForm = reactive(createEmptyPathGroup())
const pathGroupRules = {
  storage_path: [{ validator: validateStoragePath, trigger: 'blur' }]
}

const hasPathGroupData = () => pathGroupDataKeys.some((key) => String(pathGroupForm[key] || '').trim())

function validateStoragePath(_rule, value, callback) {
  if ((pathGroupForm.id || hasPathGroupData()) && !String(value || '').trim()) {
    callback(new Error('填写路径组时请输入原文路径'))
    return
  }
  callback()
}

function assignPathGroup(source = {}) {
  Object.assign(pathGroupForm, createEmptyPathGroup(), source)
  expandedSections.value = ['classification', 'paths']
  pathGroupFormRef.value?.clearValidate()
}

function resetPathGroup() {
  assignPathGroup()
}

async function loadFiles() {
  if (!props.projectId) {
    resetPathGroup()
    return
  }

  fileLoading.value = true
  try {
    const response = await getProjectFilesByProject(props.projectId, { skip: 0, limit: 1 })
    assignPathGroup(Array.isArray(response) && response.length ? response[0] : {})
  } catch (error) {
    resetPathGroup()
    ElMessage.error(error?.detail || '加载项目路径组失败')
  } finally {
    fileLoading.value = false
  }
}

async function validatePathGroup() {
  if (!canWrite.value) return true
  if (!pathGroupForm.id && !hasPathGroupData()) return true
  const valid = await pathGroupFormRef.value?.validate().catch(() => false)
  if (!valid && !expandedSections.value.includes('paths')) {
    expandedSections.value = [...expandedSections.value, 'paths']
  }
  return Boolean(valid)
}

function buildPayload(orderNo) {
  const payload = { ...pathGroupForm }
  delete payload.id
  payload.file_name = payload.file_name || orderNo || associatedOrderNo.value || '项目文件'
  pathGroupDataKeys.filter((key) => key !== 'storage_path').forEach((key) => {
    if (!payload[key]) payload[key] = null
  })
  return payload
}

function getStatusMessage(savedFile, payload) {
  if (savedFile?.project_status === 'feedback_sent_to_client' && payload.feedback_delivery_path) return '，项目状态已更新为“反馈后发客户”'
  if (savedFile?.project_status === 'client_feedback' && payload.project_feedback_path) return '，项目状态已更新为“客户反馈”'
  if (savedFile?.project_status === 'sent_to_client' && payload.client_delivery_path) return '，项目状态已更新为“已发客户”'
  if (savedFile?.project_status === 'translator_returned' && payload.translator_return_path) return '，项目状态已更新为“译员发回”'
  return ''
}

async function savePathGroup(options = {}) {
  if (!canWrite.value) return null
  if (fileSaving.value) return null
  if (!pathGroupForm.id && !hasPathGroupData()) return null

  const valid = await validatePathGroup()
  if (!valid) {
    const error = new Error('请完善项目路径组')
    error.validationFailed = true
    throw error
  }

  const targetProjectId = options.projectId || props.projectId
  const targetOrderNo = options.orderNo || associatedOrderNo.value
  if (!targetProjectId) throw new Error('请先保存项目，再关联路径组')

  fileSaving.value = true
  try {
    const payload = buildPayload(targetOrderNo)
    const savedFile = pathGroupForm.id
      ? await updateProjectFile(pathGroupForm.id, payload)
      : await createProjectFile({
          translation_project_id: targetProjectId,
          ...payload,
          uploaded_by: localStorage.getItem('user_id') || null
        })
    assignPathGroup(savedFile)
    if (savedFile?.project_status) emit('status-change', savedFile.project_status)
    if (!options.silent) {
      ElMessage.success(`路径组保存成功${getStatusMessage(savedFile, payload)}`)
    }
    return savedFile
  } catch (error) {
    if (!options.silent) ElMessage.error(getLocalizedErrorMessage(error, '路径组保存失败'))
    throw error
  } finally {
    fileSaving.value = false
  }
}

async function handlePathGroupDelete() {
  if (!pathGroupForm.id) return
  try {
    await ElMessageBox.confirm('确认清空该项目的整组文件路径吗？', '提示', { type: 'warning' })
    await deleteProjectFile(pathGroupForm.id)
    resetPathGroup()
    ElMessage.success('路径组已清空')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || '清空路径组失败')
    }
  }
}

watch(
  () => [props.projectId, props.active],
  ([projectId, active], previous = []) => {
    const [previousProjectId] = previous
    if (!projectId) {
      if (previousProjectId) resetPathGroup()
      return
    }
    if (active) loadFiles()
  },
  { immediate: true }
)

watch(
  () => pathGroupForm.translation_domain_level1,
  (value) => {
    if (!value) pathGroupForm.translation_domain_level2 = ''
  }
)

watch(
  () => pathGroupForm.file_type,
  (value) => {
    if (!value) pathGroupForm.file_type_secondary = ''
  }
)

watch(
  () => pathGroupForm.file_attribute_level1,
  (value) => {
    if (!value) {
      pathGroupForm.file_attribute_level2 = ''
      pathGroupForm.file_attribute_level3 = ''
    }
  }
)

watch(
  () => pathGroupForm.file_attribute_level2,
  (value) => {
    if (!value) pathGroupForm.file_attribute_level3 = ''
  }
)

defineExpose({
  loadFiles,
  resetPathGroup,
  savePathGroup,
  validatePathGroup
})
</script>

<style scoped>
.path-group-panel {
  min-height: 160px;
}

.files-hint {
  margin-bottom: 12px;
}

.files-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.files-description {
  margin-top: 4px;
  color: #909399;
  font-size: 13px;
}

.path-group-form {
  min-height: 120px;
}

.file-edit-collapse__title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 12px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.file-edit-collapse__hint {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-edit-collapse__body {
  padding: 16px 12px 0;
}

:deep(.file-edit-collapse .el-collapse-item__header) {
  height: 48px;
  padding: 0 12px;
  background: var(--el-fill-color-lighter);
}

:deep(.file-edit-collapse .el-collapse-item__content) {
  padding-bottom: 8px;
}

.path-group-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
}

@media (max-width: 768px) {
  .file-edit-collapse__hint {
    display: none;
  }
}
</style>
