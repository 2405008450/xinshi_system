<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>用户角色关联管理</span>
        <el-button type="primary" @click="handleAdd">新增关联</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="user_id" label="用户ID" width="300" />
      <el-table-column prop="role_id" label="角色ID" width="300" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
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
      title="新增用户角色关联"
      width="500px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="用户ID" prop="user_id">
          <el-input v-model="form.user_id" placeholder="请输入用户UUID" />
        </el-form-item>
        <el-form-item label="角色ID" prop="role_id">
          <el-input v-model="form.role_id" placeholder="请输入角色UUID" />
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
import * as userRoleApi from '@/api/userRoles'

const loading = ref(false)
const dialogVisible = ref(false)
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  user_id: '',
  role_id: ''
})

const rules = {
  user_id: [{ required: true, message: '请输入用户ID', trigger: 'blur' }],
  role_id: [{ required: true, message: '请输入角色ID', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    // 注意：这里简化处理，实际应该调用列表接口
    // 由于后端没有列表接口，这里先显示提示
    tableData.value = []
    pagination.total = 0
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该关联吗？', '提示', {
      type: 'warning'
    })
    await userRoleApi.deleteUserRole(row.id)
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
        await userRoleApi.createUserRole(form)
        ElMessage.success('创建成功')
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
    user_id: '',
    role_id: ''
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
