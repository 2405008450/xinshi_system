<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目详情</span>
        <el-button type="primary" @click="handleAdd">新增项目详情</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="project_id" label="项目ID" width="300" />
      <el-table-column prop="detail_title" label="详情标题" width="200" />
      <el-table-column prop="detail_type" label="详情类型" width="120" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
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
      width="700px"
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
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="详情标题" prop="detail_title">
              <el-input v-model="form.detail_title" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="详情类型" prop="detail_type">
              <el-input v-model="form.detail_type" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-input v-model="form.priority" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-input v-model="form.status" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="3" />
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
import * as projectDetailApi from '../api/projectDetails'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增项目详情')
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
  detail_title: '',
  detail_type: '',
  description: '',
  priority: '',
  status: '',
  remarks: ''
})

const rules = {
  project_id: [{ required: true, message: '请输入项目ID', trigger: 'blur' }],
  detail_title: [{ required: true, message: '请输入详情标题', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await projectDetailApi.getProjectDetails({
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    })
    tableData.value = res || []
    pagination.total = res?.length || 0
  } catch (error) {
    // 后端接口还未实现时，使用空数据
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增项目详情'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑项目详情'
  Object.assign(form, {
    id: row.id,
    project_id: row.project_id || '',
    detail_title: row.detail_title || '',
    detail_type: row.detail_type || '',
    description: row.description || '',
    priority: row.priority || '',
    status: row.status || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目详情吗？', '提示', {
      type: 'warning'
    })
    await projectDetailApi.deleteProjectDetail(row.id)
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
          await projectDetailApi.updateProjectDetail(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await projectDetailApi.createProjectDetail(submitData)
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
    detail_title: '',
    detail_type: '',
    description: '',
    priority: '',
    status: '',
    remarks: ''
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
