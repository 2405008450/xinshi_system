<template>
  <div v-if="!projectId">
    <el-empty description="请先选择项目" />
  </div>
  <div v-else>
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
      <el-table-column label="发客户路径" min-width="220">
        <template #default="{ row }">
          <template v-if="row.client_delivery_path">
            <a :href="toOpenPathHref(row.client_delivery_path)" class="path-link">{{ row.client_delivery_path }}</a>
            <el-button link type="primary" size="small" style="margin-left: 4px" @click.prevent="copyFilePath(row.client_delivery_path)">复制</el-button>
          </template>
          <span v-else class="path-empty">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="updatedAt" label="创建时间" width="170" />
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="handleFileEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" link @click="handleFileDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!fileListLoading && !fileList.length" description="该项目暂无文件记录" />

    <el-dialog v-model="fileEditDialogVisible" title="编辑项目文件" width="560px" @close="resetFileEditForm">
      <el-form ref="fileEditFormRef" :model="fileEditForm" :rules="fileEditRules" label-width="110px">
        <el-form-item label="文件名" prop="file_name">
          <el-input v-model="fileEditForm.file_name" placeholder="请输入文件名" />
        </el-form-item>
        <el-form-item label="原文路径" prop="storage_path">
          <el-input v-model="fileEditForm.storage_path" placeholder="如 \\win-server\原文" />
        </el-form-item>
        <el-form-item label="派稿文路径">
          <el-input v-model="fileEditForm.dispatch_path" placeholder="如 \\win-server\派稿" />
        </el-form-item>
        <el-form-item label="译文路径">
          <el-input v-model="fileEditForm.translation_path" placeholder="如 \\win-server\译文" />
        </el-form-item>
        <el-form-item label="发客户路径">
          <el-input v-model="fileEditForm.client_delivery_path" placeholder="如 \\win-server\发客户" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fileEditDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="fileEditSaving" @click="handleFileEditSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { deleteProjectFile, getProjectFilesByProject, updateProjectFile } from '@/api/projectFiles'

const props = defineProps({
  projectId: {
    type: [String, Number],
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

const fileList = ref([])
const fileListLoading = ref(false)
const fileEditDialogVisible = ref(false)
const fileEditSaving = ref(false)
const fileEditFormRef = ref(null)
const fileEditForm = reactive({
  id: null,
  file_name: '',
  storage_path: '',
  dispatch_path: '',
  translation_path: '',
  client_delivery_path: ''
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
    client_delivery_path: row.client_delivery_path || ''
  })
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
  await fileEditFormRef.value.validate(async (valid) => {
    if (!valid) return

    fileEditSaving.value = true
    try {
      const payload = { ...fileEditForm }
      delete payload.id
      ;['dispatch_path', 'translation_path', 'client_delivery_path'].forEach((key) => {
        if (!payload[key]) payload[key] = null
      })
      await updateProjectFile(fileEditForm.id, payload)
      ElMessage.success('更新成功')
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
    client_delivery_path: ''
  })
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

defineExpose({
  loadFiles
})
</script>

<style scoped>
.files-hint {
  margin-bottom: 12px;
}

.path-link {
  word-break: break-all;
  color: #409eff;
  text-decoration: none;
  font-size: 12px;
}

.path-empty {
  color: #c0c4cc;
}
</style>
