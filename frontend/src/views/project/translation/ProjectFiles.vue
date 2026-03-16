<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目文件</span>
        <el-button type="primary" @click="handleAdd">新增文件</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-form">
      <el-form-item label="项目 ID">
        <el-input v-model="projectIdFilter" clearable placeholder="请输入项目 UUID" style="width: 360px" @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="file_name" label="文件名" min-width="220" />
      <el-table-column prop="translation_project_id" label="项目 ID" min-width="300" show-overflow-tooltip />
      <el-table-column prop="file_type" label="类型" width="120" />
      <el-table-column prop="file_ext" label="扩展名" width="100" />
      <el-table-column prop="file_size" label="大小" width="120">
        <template #default="{ row }">
          {{ row.file_size ? formatFileSize(row.file_size) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="storage_type" label="存储类型" width="120" />
      <el-table-column label="网络路径" min-width="260">
        <template #default="{ row }">
          <template v-if="row.storage_path">
            <a :href="getOpenPathHref(row.storage_path)" style="word-break: break-all; color: #409eff; text-decoration: none; font-size: 12px;">
              {{ row.storage_path }}
            </a>
            <el-button
              link
              type="primary"
              size="small"
              style="margin-left: 6px;"
              @click.prevent="copyPath(row.storage_path)"
            >复制</el-button>
          </template>
          <span v-else style="color: #c0c4cc;">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="fetchData"
      @current-change="fetchData"
      style="margin-top: 20px"
    />

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="项目 ID" prop="translation_project_id">
          <el-input v-model="form.translation_project_id" placeholder="请输入项目 UUID" />
        </el-form-item>
        <el-form-item label="文件名" prop="file_name">
          <el-input v-model="form.file_name" />
        </el-form-item>
        <el-form-item label="网络共享路径" prop="storage_path">
          <el-input v-model="form.storage_path" placeholder="请输入 UNC 路径，如 \\server\share\folder" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="文件类型" prop="file_type">
              <el-input v-model="form.file_type" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文件扩展名" prop="file_ext">
              <el-input v-model="form.file_ext" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="文件大小" prop="file_size">
              <el-input-number v-model="form.file_size" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="存储类型" prop="storage_type">
              <el-input v-model="form.storage_type" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as projectFileApi from '@/api/projectFiles'

const route = useRoute()
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增文件')
const formRef = ref(null)
const projectIdFilter = ref('')

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  translation_project_id: '',
  file_name: '',
  storage_path: '',
  file_type: '',
  file_ext: '',
  file_size: null,
  storage_type: '',
  uploaded_by: null
})

const rules = {
  translation_project_id: [{ required: true, message: 'Project ID is required', trigger: 'blur' }],
  file_name: [{ required: true, message: 'File name is required', trigger: 'blur' }],
  storage_path: [{ required: true, message: 'Storage path is required', trigger: 'blur' }]
}

const getOpenPathHref = (path) => {
  if (!path) return '#'
  // Strip leading \\ before encoding so the URL authority part stays clean:
  // \\server\share\folder → openpath://server/share/folder
  // VBS will re-add \\ when decoding
  const stripped = path.replace(/^\\\\/, '')
  return 'openpath://' + stripped.replace(/\\/g, '/')
}

const copyPath = (path) => {
  navigator.clipboard.writeText(path)
  ElMessage.success('路径已复制')
}

const formatFileSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }

    if (projectIdFilter.value) {
      const [res, countRes] = await Promise.all([
        projectFileApi.getProjectFilesByProject(projectIdFilter.value, params),
        projectFileApi.getProjectFileCountByProject(projectIdFilter.value)
      ])
      tableData.value = Array.isArray(res) ? res : []
      pagination.total = countRes?.total || tableData.value.length
    } else {
      const [res, countRes] = await Promise.all([
        projectFileApi.getProjectFiles(params),
        projectFileApi.getProjectFileCount()
      ])
      tableData.value = Array.isArray(res) ? res : []
      pagination.total = countRes?.total || tableData.value.length
    }
  } catch (error) {
    tableData.value = []
    pagination.total = 0
    ElMessage.error(error.detail || '\u52A0\u8F7D\u6587\u4EF6\u5931\u8D25')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const resetSearch = () => {
  projectIdFilter.value = ''
  handleSearch()
}

const handleAdd = () => {
  dialogTitle.value = '新增文件'
  resetForm()
  if (projectIdFilter.value) {
    form.translation_project_id = projectIdFilter.value
  }
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑文件'
  Object.assign(form, {
    id: row.id,
    translation_project_id: row.translation_project_id,
    file_name: row.file_name,
    storage_path: row.storage_path,
    file_type: row.file_type || '',
    file_ext: row.file_ext || '',
    file_size: row.file_size || null,
    storage_type: row.storage_type || '',
    uploaded_by: row.uploaded_by
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('Delete this file?', 'Confirm', { type: 'warning' })
    await projectFileApi.deleteProjectFile(row.id)
    ElMessage.success('Deleted')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.detail || 'Delete failed')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      const submitData = { ...form }
      delete submitData.id
      if (form.id) {
        await projectFileApi.updateProjectFile(form.id, submitData)
        ElMessage.success('Updated')
      } else {
        await projectFileApi.createProjectFile(submitData)
        ElMessage.success('Created')
      }
      dialogVisible.value = false
      fetchData()
    } catch (error) {
      ElMessage.error(error.detail || 'Save failed')
    }
  })
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    translation_project_id: '',
    file_name: '',
    storage_path: '',
    file_type: '',
    file_ext: '',
    file_size: null,
    storage_type: '',
    uploaded_by: null
  })
  formRef.value?.resetFields()
}

onMounted(() => {
  const routeProjectId = Array.isArray(route.query.projectId) ? route.query.projectId[0] : route.query.projectId
  if (routeProjectId) {
    projectIdFilter.value = routeProjectId
  }
  fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}
</style>
