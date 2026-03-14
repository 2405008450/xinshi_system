<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>&#x9879;&#x76EE;&#x6587;&#x4EF6;</span>
        <el-button type="primary" @click="handleAdd">&#x65B0;&#x589E;&#x6587;&#x4EF6;</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-form">
      <el-form-item label="&#x9879;&#x76EE; ID">
        <el-input v-model="projectIdFilter" clearable placeholder="&#x8BF7;&#x8F93;&#x5165;&#x9879;&#x76EE; UUID" style="width: 360px" @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">&#x641C;&#x7D22;</el-button>
        <el-button @click="resetSearch">&#x91CD;&#x7F6E;</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="file_name" label="&#x6587;&#x4EF6;&#x540D;" min-width="220" />
      <el-table-column prop="translation_project_id" label="&#x9879;&#x76EE; ID" min-width="300" show-overflow-tooltip />
      <el-table-column prop="file_type" label="&#x7C7B;&#x578B;" width="120" />
      <el-table-column prop="file_ext" label="&#x6269;&#x5C55;&#x540D;" width="100" />
      <el-table-column prop="file_size" label="&#x5927;&#x5C0F;" width="120">
        <template #default="{ row }">
          {{ row.file_size ? formatFileSize(row.file_size) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="storage_type" label="&#x5B58;&#x50A8;&#x7C7B;&#x578B;" width="120" />
      <el-table-column prop="created_at" label="&#x521B;&#x5EFA;&#x65F6;&#x95F4;" width="180" />
      <el-table-column label="&#x64CD;&#x4F5C;" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">&#x7F16;&#x8F91;</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">&#x5220;&#x9664;</el-button>
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
        <el-form-item label="&#x9879;&#x76EE; ID" prop="translation_project_id">
          <el-input v-model="form.translation_project_id" placeholder="&#x8BF7;&#x8F93;&#x5165;&#x9879;&#x76EE; UUID" />
        </el-form-item>
        <el-form-item label="???" prop="file_name">
          <el-input v-model="form.file_name" />
        </el-form-item>
        <el-form-item label="&#x5B58;&#x50A8;&#x8DEF;&#x5F84;" prop="storage_path">
          <el-input v-model="form.storage_path" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="&#x6587;&#x4EF6;&#x7C7B;&#x578B;" prop="file_type">
              <el-input v-model="form.file_type" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="&#x6587;&#x4EF6;&#x6269;&#x5C55;&#x540D;" prop="file_ext">
              <el-input v-model="form.file_ext" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="&#x6587;&#x4EF6;&#x5927;&#x5C0F;" prop="file_size">
              <el-input-number v-model="form.file_size" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="&#x5B58;&#x50A8;&#x7C7B;&#x578B;" prop="storage_type">
              <el-input v-model="form.storage_type" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">&#x53D6;&#x6D88;</el-button>
        <el-button type="primary" @click="handleSubmit">&#x4FDD;&#x5B58;</el-button>
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
const dialogTitle = ref('Add File')
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
  dialogTitle.value = 'Add File'
  resetForm()
  if (projectIdFilter.value) {
    form.translation_project_id = projectIdFilter.value
  }
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = 'Edit File'
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
