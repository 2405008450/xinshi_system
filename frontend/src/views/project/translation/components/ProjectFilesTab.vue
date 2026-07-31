<template>
  <div v-if="!projectId">
    <el-empty description="请先选择项目" />
  </div>
  <div v-else>
    <div class="files-header">
      <div>
        <strong>关联订单：{{ associatedOrderNo || '-' }}</strong>
        <div class="files-description">文件记录固定归属于当前订单，不能单独选择或修改订单号。</div>
      </div>
      <el-button
        v-if="canWrite && !fileListLoading && fileList.length === 0"
        type="primary"
        @click="handleFileCreate"
      >
        新增文件记录
      </el-button>
    </div>

    <el-alert
      v-if="entityType === 'suborder'"
      type="info"
      :closable="false"
      class="files-hint"
      title="当前查看的是子订单，文件列表展示所属母订单的项目文件。"
    />

    <el-table :data="fileList" v-loading="fileListLoading" border size="small" style="width: 100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="name" label="文件名" min-width="160" show-overflow-tooltip />
      <el-table-column label="翻译文本领域" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatHierarchy(row.translation_domain_level1, row.translation_domain_level2) }}
        </template>
      </el-table-column>
      <el-table-column label="文件类型" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatHierarchy(row.file_type, row.file_type_secondary) }}
        </template>
      </el-table-column>
      <el-table-column label="文件格式" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.file_format || '—' }}</template>
      </el-table-column>
      <el-table-column label="文件属性" min-width="210" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatHierarchy(row.file_attribute_level1, row.file_attribute_level2, row.file_attribute_level3) }}
        </template>
      </el-table-column>
      <el-table-column label="文件难度" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.file_difficulty || '—' }}</template>
      </el-table-column>
      <el-table-column label="原文路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.storage_path">
            <a :href="toOpenPathHref(row.storage_path)" class="path-link">{{ row.storage_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.storage_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column label="派稿文路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.dispatch_path">
            <a :href="toOpenPathHref(row.dispatch_path)" class="path-link">{{ row.dispatch_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.dispatch_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column label="译员发回路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.translator_return_path">
            <a :href="toOpenPathHref(row.translator_return_path)" class="path-link">{{ row.translator_return_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.translator_return_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column label="发客户路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.client_delivery_path">
            <a :href="toOpenPathHref(row.client_delivery_path)" class="path-link">{{ row.client_delivery_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.client_delivery_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column label="项目反馈路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.project_feedback_path">
            <a :href="toOpenPathHref(row.project_feedback_path)" class="path-link">{{ row.project_feedback_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.project_feedback_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column label="反馈后发客户路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.feedback_delivery_path">
            <a :href="toOpenPathHref(row.feedback_delivery_path)" class="path-link">{{ row.feedback_delivery_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.feedback_delivery_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="updatedAt" label="创建时间" width="170" />
      <el-table-column v-if="canWrite" label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="handleFileEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" link @click="handleFileDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!fileListLoading && !fileList.length" description="该项目暂无文件记录" />

    <el-dialog
      v-model="fileEditDialogVisible"
      :title="fileEditForm.id ? '编辑项目文件' : '新增项目文件'"
      width="860px"
      append-to-body
      @close="resetFileEditForm"
    >
      <el-alert
        :title="`关联订单：${associatedOrderNo || '-'}`"
        type="info"
        :closable="false"
        show-icon
        class="order-alert"
      />
      <el-form ref="fileEditFormRef" :model="fileEditForm" :rules="fileEditRules" label-width="110px">
        <el-divider content-position="left">基础信息</el-divider>
        <el-form-item label="文件名" prop="file_name">
          <el-input v-model="fileEditForm.file_name" placeholder="请输入文件名" />
        </el-form-item>

        <el-collapse v-model="fileEditExpandedSections" class="file-edit-collapse">
          <el-collapse-item name="classification">
            <template #title>
              <div class="file-edit-collapse__title">
                <span>文件分类</span>
                <span class="file-edit-collapse__hint">领域、类型、格式、属性和难度</span>
              </div>
            </template>
            <div class="file-edit-collapse__body">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="文本领域一级">
                    <el-input v-model="fileEditForm.translation_domain_level1" clearable placeholder="请输入一级领域" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="文本领域二级">
                    <el-input
                      v-model="fileEditForm.translation_domain_level2"
                      clearable
                      :disabled="!fileEditForm.translation_domain_level1"
                      placeholder="请输入二级领域"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="文件类型一级">
                    <el-input v-model="fileEditForm.file_type" clearable placeholder="请输入一级类型" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="文件类型二级">
                    <el-input
                      v-model="fileEditForm.file_type_secondary"
                      clearable
                      :disabled="!fileEditForm.file_type"
                      placeholder="请输入二级类型"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="文件格式">
                    <el-input v-model="fileEditForm.file_format" clearable placeholder="如 DOCX、PDF、XLSX" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="文件难度">
                    <el-input v-model="fileEditForm.file_difficulty" clearable placeholder="请输入文件难度" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="文件属性一级">
                    <el-input v-model="fileEditForm.file_attribute_level1" clearable placeholder="一级属性" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="文件属性二级">
                    <el-input
                      v-model="fileEditForm.file_attribute_level2"
                      clearable
                      :disabled="!fileEditForm.file_attribute_level1"
                      placeholder="二级属性"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="文件属性三级">
                    <el-input
                      v-model="fileEditForm.file_attribute_level3"
                      clearable
                      :disabled="!fileEditForm.file_attribute_level2"
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
                <span class="file-edit-collapse__hint">原文路径必填，其他路径按流程补充</span>
              </div>
            </template>
            <div class="file-edit-collapse__body">
              <el-form-item label="原文路径" prop="storage_path">
                <el-input v-model="fileEditForm.storage_path" placeholder="如 \\win-server\原文" />
              </el-form-item>
              <el-form-item label="派稿文路径">
                <el-input v-model="fileEditForm.dispatch_path" placeholder="如 \\win-server\派稿" />
              </el-form-item>
              <el-form-item label="译文路径">
                <el-input v-model="fileEditForm.translation_path" placeholder="如 \\win-server\译文" />
              </el-form-item>
              <el-form-item label="译员发回路径">
                <el-input v-model="fileEditForm.translator_return_path" placeholder="填写后项目状态自动变为“译员发回”" />
              </el-form-item>
              <el-form-item label="发客户路径">
                <el-input v-model="fileEditForm.client_delivery_path" placeholder="填写后项目状态自动变为“已发客户”" />
              </el-form-item>
              <el-form-item label="项目反馈路径">
                <el-input v-model="fileEditForm.project_feedback_path" placeholder="填写后项目状态自动变为“客户反馈”" />
              </el-form-item>
              <el-form-item label="反馈后发客户路径">
                <el-input v-model="fileEditForm.feedback_delivery_path" placeholder="填写后项目状态自动变为“反馈后发客户”" />
              </el-form-item>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="fileEditDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="fileEditSaving" @click="handleFileEditSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createProjectFile, deleteProjectFile, getProjectFilesByProject, updateProjectFile } from '@/api/projectFiles'
import { hasPermission } from '@/utils/permission'

const emit = defineEmits(['status-change'])
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
  }
})

const canWrite = computed(() => hasPermission('project_files:write'))
const fileList = ref([])
const associatedOrderNo = computed(() => props.orderNo || fileList.value[0]?.order_no || '')
const fileListLoading = ref(false)
const fileEditDialogVisible = ref(false)
const fileEditSaving = ref(false)
const fileEditFormRef = ref(null)
const fileEditExpandedSections = ref(['classification', 'paths'])
const fileEditForm = reactive({
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
const fileEditRules = {
  file_name: [{ required: true, message: '请输入文件名', trigger: 'blur' }],
  storage_path: [{ required: true, message: '请输入原文路径', trigger: 'blur' }]
}

const normalizeProjectFile = (file) => ({
  ...file,
  name: file?.file_name || '-',
  updatedAt: file?.created_at ? String(file.created_at).replace('T', ' ').substring(0, 19) : '-'
})

function formatHierarchy(...values) {
  const normalized = values.filter((value) => String(value || '').trim())
  return normalized.length ? normalized.join(' / ') : '—'
}

function toOpenPathHref(path) {
  if (!path) return '#'
  const stripped = path.replace(/^\\\\/, '')
  return `openpath://${encodeURIComponent(stripped).replace(/%5C/gi, '\\').replace(/%2F/gi, '/')}`
}

async function copyFilePath(path) {
  if (!path) return
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success('路径已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

async function loadFiles() {
  if (!props.projectId) {
    fileList.value = []
    return
  }

  fileListLoading.value = true
  try {
    const response = await getProjectFilesByProject(props.projectId, { skip: 0, limit: 100 })
    fileList.value = (Array.isArray(response) ? response : []).map(normalizeProjectFile)
  } catch {
    fileList.value = []
  } finally {
    fileListLoading.value = false
  }
}

function handleFileEdit(row) {
  Object.assign(fileEditForm, {
    id: row.id,
    file_name: row.file_name || '',
    storage_path: row.storage_path || '',
    dispatch_path: row.dispatch_path || '',
    translation_path: row.translation_path || '',
    translator_return_path: row.translator_return_path || '',
    client_delivery_path: row.client_delivery_path || '',
    project_feedback_path: row.project_feedback_path || '',
    feedback_delivery_path: row.feedback_delivery_path || '',
    translation_domain_level1: row.translation_domain_level1 || '',
    translation_domain_level2: row.translation_domain_level2 || '',
    file_type: row.file_type || '',
    file_type_secondary: row.file_type_secondary || '',
    file_format: row.file_format || '',
    file_attribute_level1: row.file_attribute_level1 || '',
    file_attribute_level2: row.file_attribute_level2 || '',
    file_attribute_level3: row.file_attribute_level3 || '',
    file_difficulty: row.file_difficulty || ''
  })
  fileEditExpandedSections.value = ['classification', 'paths']
  fileEditDialogVisible.value = true
}

function handleFileCreate() {
  resetFileEditForm()
  fileEditDialogVisible.value = true
}

async function handleFileDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该文件记录？', '提示', { type: 'warning' })
    await deleteProjectFile(row.id)
    ElMessage.success('删除成功')
    await loadFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.detail || '删除失败')
    }
  }
}

async function handleFileEditSubmit() {
  if (!fileEditFormRef.value) return
  await fileEditFormRef.value.validate(async (valid, invalidFields) => {
    if (!valid) {
      if (
        invalidFields?.storage_path &&
        !fileEditExpandedSections.value.includes('paths')
      ) {
        fileEditExpandedSections.value = [...fileEditExpandedSections.value, 'paths']
      }
      return
    }

    fileEditSaving.value = true
    try {
      const payload = { ...fileEditForm }
      delete payload.id
      ;[
        'dispatch_path',
        'translation_path',
        'translator_return_path',
        'client_delivery_path',
        'project_feedback_path',
        'feedback_delivery_path',
        'translation_domain_level1',
        'translation_domain_level2',
        'file_type',
        'file_type_secondary',
        'file_format',
        'file_attribute_level1',
        'file_attribute_level2',
        'file_attribute_level3',
        'file_difficulty'
      ].forEach((key) => {
        if (!payload[key]) payload[key] = null
      })
      let savedFile
      if (fileEditForm.id) {
        savedFile = await updateProjectFile(fileEditForm.id, payload)
      } else {
        savedFile = await createProjectFile({
          translation_project_id: props.projectId,
          ...payload,
          uploaded_by: localStorage.getItem('user_id') || null
        })
      }
      if (savedFile?.project_status) {
        emit('status-change', savedFile.project_status)
      }
      const statusMessage =
        savedFile?.project_status === 'feedback_sent_to_client' && payload.feedback_delivery_path
          ? '，项目状态已更新为“反馈后发客户”'
          : savedFile?.project_status === 'client_feedback' && payload.project_feedback_path
            ? '，项目状态已更新为“客户反馈”'
            : savedFile?.project_status === 'sent_to_client' && payload.client_delivery_path
              ? '，项目状态已更新为“已发客户”'
              : savedFile?.project_status === 'translator_returned' && payload.translator_return_path
                ? '，项目状态已更新为“译员发回”'
                : ''
      ElMessage.success(
        `${fileEditForm.id ? '更新成功' : '文件记录已关联到当前订单'}${statusMessage}`
      )
      fileEditDialogVisible.value = false
      await loadFiles()
    } catch (error) {
      ElMessage.error(error?.detail || '保存失败')
    } finally {
      fileEditSaving.value = false
    }
  })
}

function resetFileEditForm() {
  Object.assign(fileEditForm, {
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
  fileEditExpandedSections.value = ['classification', 'paths']
  fileEditFormRef.value?.resetFields()
}

watch(
  () => [props.projectId, props.active],
  ([projectId, active]) => {
    if (!projectId) {
      fileList.value = []
      return
    }
    if (active) {
      loadFiles()
    }
  },
  { immediate: true }
)

watch(
  () => fileEditForm.translation_domain_level1,
  (value) => {
    if (!value) fileEditForm.translation_domain_level2 = ''
  }
)

watch(
  () => fileEditForm.file_type,
  (value) => {
    if (!value) fileEditForm.file_type_secondary = ''
  }
)

watch(
  () => fileEditForm.file_attribute_level1,
  (value) => {
    if (!value) {
      fileEditForm.file_attribute_level2 = ''
      fileEditForm.file_attribute_level3 = ''
    }
  }
)

watch(
  () => fileEditForm.file_attribute_level2,
  (value) => {
    if (!value) fileEditForm.file_attribute_level3 = ''
  }
)

defineExpose({
  loadFiles
})
</script>

<style scoped>
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

.order-alert {
  margin-bottom: 16px;
}

.file-edit-collapse {
  margin-top: 16px;
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

.path-link {
  word-break: break-all;
  color: var(--color-primary);
  text-decoration: none;
  font-size: 12px;
}

.path-empty {
  color: var(--color-text-muted);
}

</style>
