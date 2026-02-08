<template>
  <el-card class="page-card">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><Folder /></el-icon>
          <span class="header-title">项目管理</span>
        </div>
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增项目</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="project_no" label="项目编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="150" />
      <el-table-column prop="project_type" label="项目类型" width="120" />
      <el-table-column prop="source_language" label="源语言" width="100" />
      <el-table-column prop="target_language" label="目标语言" width="100" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="deadline" label="截止日期" width="120" />
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
      width="700px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目编号" prop="project_no">
              <el-input v-model="form.project_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户名称" prop="client_name">
              <el-input v-model="form.client_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目类型" prop="project_type">
              <el-input v-model="form.project_type" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-input v-model="form.status" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="源语言" prop="source_language">
              <el-input v-model="form.source_language" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标语言" prop="target_language">
              <el-input v-model="form.target_language" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="字数" prop="word_count">
              <el-input v-model="form.word_count" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期" prop="deadline">
              <el-input v-model="form.deadline" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="销售负责人" prop="sales_owner">
          <el-input v-model="form.sales_owner" />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="4" />
        </el-form-item>
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
import { Folder, Plus } from '@element-plus/icons-vue'
import * as projectApi from '@/api/projects'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增项目')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  project_no: '',
  client_name: '',
  project_type: '',
  source_language: '',
  target_language: '',
  word_count: '',
  deadline: '',
  status: '',
  sales_owner: '',
  remarks: '',
  created_by: null
})

const rules = {
  project_no: [{ required: true, message: '请输入项目编号', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await projectApi.getProjects({
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
  dialogTitle.value = '新增项目'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑项目'
  Object.assign(form, {
    id: row.id,
    project_no: row.project_no,
    client_name: row.client_name || '',
    project_type: row.project_type || '',
    source_language: row.source_language || '',
    target_language: row.target_language || '',
    word_count: row.word_count || '',
    deadline: row.deadline || '',
    status: row.status || '',
    sales_owner: row.sales_owner || '',
    remarks: row.remarks || '',
    created_by: row.created_by
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目吗？', '提示', {
      type: 'warning'
    })
    await projectApi.deleteProject(row.id)
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
          await projectApi.updateProject(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await projectApi.createProject(submitData)
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
    project_no: '',
    client_name: '',
    project_type: '',
    source_language: '',
    target_language: '',
    word_count: '',
    deadline: '',
    status: '',
    sales_owner: '',
    remarks: '',
    created_by: null
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
