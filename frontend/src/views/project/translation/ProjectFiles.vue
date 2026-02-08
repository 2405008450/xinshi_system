<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目文件管理</span>
        <el-button type="primary" @click="handleAdd">新增文件</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="file_name" label="文件名" width="200" />
      <el-table-column prop="project_id" label="项目ID" width="300" />
      <el-table-column prop="file_type" label="文件类型" width="120" />
      <el-table-column prop="file_ext" label="扩展名" width="100" />
      <el-table-column prop="file_size" label="文件大小" width="120">
        <template #default="{ row }">
          {{ row.file_size ? formatFileSize(row.file_size) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="storage_type" label="存储类型" width="120" />
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

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
      >
        <el-form-item label="项目ID" prop="project_id">
          <el-input v-model="form.project_id" placeholder="请输入项目UUID" />
        </el-form-item>
        <el-form-item label="文件名" prop="file_name">
          <el-input v-model="form.file_name" />
        </el-form-item>
        <el-form-item label="存储路径" prop="storage_path">
          <el-input v-model="form.storage_path" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="文件类型" prop="file_type">
              <el-input v-model="form.file_type" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="扩展名" prop="file_ext">
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
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as projectFileApi from '@/api/projectFiles'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增文件')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  project_id: '',
  file_name: '',
  storage_path: '',
  file_type: '',
  file_ext: '',
  file_size: null,
  storage_type: '',
  uploaded_by: null
})

const rules = {
  project_id: [{ required: true, message: '请输入项目ID', trigger: 'blur' }],
  file_name: [{ required: true, message: '请输入文件名', trigger: 'blur' }],
  storage_path: [{ required: true, message: '请输入存储路径', trigger: 'blur' }]
}

const formatFileSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await projectFileApi.getProjectFiles({
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    })
    tableData.value = res
    pagination.total = res.length
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增文件'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑文件'
  Object.assign(form, {
    id: row.id,
    project_id: row.project_id,
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
    await ElMessageBox.confirm('确定要删除该文件吗？', '提示', {
      type: 'warning'
    })
    await projectFileApi.deleteProjectFile(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const submitData = { ...form }
        delete submitData.id
        if (form.id) {
          await projectFileApi.updateProjectFile(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await projectFileApi.createProjectFile(submitData)
          ElMessage.success('创建成功')
        }
        dialogVisible.value = false
        fetchData()
      } catch (error) {
        ElMessage.error(error.detail || '操作失败')
      }
    }
  })
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    project_id: '',
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
  fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
