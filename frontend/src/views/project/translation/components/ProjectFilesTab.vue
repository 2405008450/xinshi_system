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

    <el-alert v-if="fileLoadError" type="error" :closable="false" show-icon>
      <template #title>{{ fileLoadError }}</template>
      <el-button :loading="fileLoading" @click="loadFiles">重新加载</el-button>
    </el-alert>

    <AppForm
      v-if="sourceFileName !== undefined"
      :model="{ sourceFileName }"
      :disabled="!sourceFileNameEditable"
      label-width="130px"
      class="source-file-name-form"
    >
      <el-form-item label="母订单文件名称">
        <div class="source-file-name-field">
          <el-input
            :model-value="sourceFileName"
            clearable
            maxlength="255"
            show-word-limit
            placeholder="请输入该母订单对应的真实文件名称，供后续对账使用"
            @update:model-value="emit('update:sourceFileName', $event)"
          />
          <div class="source-file-name-hint">填写原文路径后自动读取当前目录第一层文件；多个文件以中文分号分隔。</div>
        </div>
      </el-form-item>
    </AppForm>

    <AppForm
      ref="pathGroupFormRef"
      v-loading="fileLoading"
      :model="pathGroupForm"
      :rules="pathGroupRules"
      :disabled="!canWrite || fileLoading || Boolean(fileLoadError)"
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
              <el-input
                v-model="pathGroupForm.storage_path"
                placeholder="如 \\win-server\原文"
                @blur="handleSourcePathBlur"
              >
                <template #append>
                  <el-button
                    :loading="sourceNameLoading"
                    :disabled="!canWrite || !String(pathGroupForm.storage_path || '').trim()"
                    @click="handleSourceNameReload"
                  >
                    读取文件名
                  </el-button>
                </template>
              </el-input>
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
    </AppForm>

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
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createProjectFile,
  deleteProjectFile,
  getProjectFilesByProject,
  inspectProjectSourcePath,
  updateProjectFile
} from '@/api/projectFiles'
import { hasPermission } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const emit = defineEmits(['status-change', 'update:referenceFilePathOne', 'update:sourceFileName'])
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
  },
  sourceFileName: {
    type: String,
    default: undefined
  },
  sourceFileNameEditable: {
    type: Boolean,
    default: false
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
const fileLoadError = ref('')
let fileRequestId = 0
let loadedProjectId = null
const fileSaving = ref(false)
const sourceNameLoading = ref(false)
const lastInspectedStoragePath = ref('')
let sourceNameRequest = null
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
  lastInspectedStoragePath.value = props.sourceFileName
    ? String(source.storage_path || '').trim()
    : ''
  expandedSections.value = ['classification', 'paths']
  pathGroupFormRef.value?.clearValidate()
}

async function fillSourceFileNameFromPath({ force = false, notifySuccess = true, notifyError = true } = {}) {
  const storagePath = String(pathGroupForm.storage_path || '').trim()
  if (!storagePath) return null
  if (!force && storagePath === lastInspectedStoragePath.value) return props.sourceFileName || null
  if (sourceNameRequest) return sourceNameRequest

  sourceNameLoading.value = true
  sourceNameRequest = inspectProjectSourcePath(storagePath)
    .then((response) => {
      emit('update:sourceFileName', response.source_file_name || '')
      lastInspectedStoragePath.value = storagePath
      if (notifySuccess) {
        ElMessage.success(`已从原文路径读取 ${response.file_count} 个文件名`)
      }
      return response
    })
    .catch((error) => {
      if (notifyError) ElMessage.error(getLocalizedErrorMessage(error, '读取原文路径中的文件名失败'))
      throw error
    })
    .finally(() => {
      sourceNameLoading.value = false
      sourceNameRequest = null
    })
  return sourceNameRequest
}

function handleSourcePathBlur() {
  void fillSourceFileNameFromPath({ notifySuccess: false }).catch(() => {})
}

function handleSourceNameReload() {
  void fillSourceFileNameFromPath({ force: true }).catch(() => {})
}

function resetPathGroup() {
  // 重置时使上一次请求失效，避免关闭或切换订单后回填旧数据。
  fileRequestId += 1
  loadedProjectId = null
  fileLoading.value = false
  fileLoadError.value = ''
  assignPathGroup()
}

async function loadFiles() {
  if (!props.projectId) {
    resetPathGroup()
    return
  }

  const projectId = props.projectId
  const requestId = ++fileRequestId
  fileLoading.value = true
  fileLoadError.value = ''
  try {
    const response = await getProjectFilesByProject(projectId, { skip: 0, limit: 1 })
    if (requestId !== fileRequestId || projectId !== props.projectId) return
    assignPathGroup(Array.isArray(response) && response.length ? response[0] : {})
    loadedProjectId = projectId
  } catch (error) {
    if (requestId !== fileRequestId || projectId !== props.projectId) return
    fileLoadError.value = getLocalizedErrorMessage(error, '加载项目路径组失败，请重新加载')
  } finally {
    if (requestId === fileRequestId) fileLoading.value = false
  }
}

async function validatePathGroup() {
  if (fileLoading.value || fileLoadError.value) {
    ElMessage.warning(fileLoading.value ? '项目文件正在加载，请稍后保存' : '请先重新加载项目文件，再保存')
    return false
  }
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
    if (projectId !== previousProjectId) resetPathGroup()
    if (!projectId) return
    // 页签往返保留尚未保存的输入；失败后再次进入仍可重试。
    if (active && loadedProjectId !== projectId && !fileLoading.value) void loadFiles()
  },
  { immediate: true }
)

onBeforeUnmount(() => { fileRequestId += 1 })

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
  fillSourceFileNameFromPath,
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

.source-file-name-form {
  margin-top: 16px;
  padding: 16px 16px 2px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}

.source-file-name-field {
  width: 100%;
}

.source-file-name-hint {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
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
