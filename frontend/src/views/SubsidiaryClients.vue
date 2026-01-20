<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>子公司客户信息</span>
        <el-button type="primary" @click="handleAdd">新增子公司客户</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="200" />
      <el-table-column prop="client_short_name" label="客户简称" width="150" />
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
        label-width="140px"
      >
        <el-form-item label="客户编号" prop="client_code">
          <el-select
            v-model="form.client_code"
            filterable
            remote
            :remote-method="searchClients"
            placeholder="请选择或搜索客户编号"
            style="width: 100%"
            @change="handleClientChange"
          >
            <el-option
              v-for="client in clientOptions"
              :key="client.client_code"
              :label="`${client.client_code} - ${client.client_name}`"
              :value="client.client_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="客户名称" prop="client_name">
          <el-input v-model="form.client_name" :disabled="true" />
        </el-form-item>
        <el-form-item label="客户简称" prop="client_short_name">
          <el-input v-model="form.client_short_name" :disabled="true" />
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
import * as subsidiaryClientApi from '../api/subsidiaryClients'
import * as clientApi from '../api/clients'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增子公司客户')
const formRef = ref(null)
const clientOptions = ref([])

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  client_code: '',
  client_name: '',
  client_short_name: ''
})

const rules = {
  client_code: [{ required: true, message: '请选择客户编号', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await subsidiaryClientApi.getSubsidiaryClients({
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    })
    tableData.value = res || []
    pagination.total = res?.length || 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const searchClients = async (query) => {
  if (!query) {
    clientOptions.value = []
    return
  }
  try {
    const res = await clientApi.getClients({ skip: 0, limit: 20 })
    clientOptions.value = res?.filter(client => 
      client.client_code?.includes(query) || 
      client.client_name?.includes(query)
    ) || []
  } catch (error) {
    clientOptions.value = []
  }
}

const handleClientChange = async (clientCode) => {
  if (!clientCode) return
  try {
    const clients = await clientApi.getClients({ skip: 0, limit: 100 })
    const client = clients?.find(c => c.client_code === clientCode)
    if (client) {
      form.client_name = client.client_name || ''
      form.client_short_name = client.client_short_name || ''
    }
  } catch (error) {
    console.error('获取客户信息失败', error)
  }
}

const handleAdd = async () => {
  dialogTitle.value = '新增子公司客户'
  resetForm()
  // 加载客户列表
  try {
    const res = await clientApi.getClients({ skip: 0, limit: 100 })
    clientOptions.value = res || []
  } catch (error) {
    clientOptions.value = []
  }
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑子公司客户'
  Object.assign(form, {
    id: row.id,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该子公司客户吗？', '提示', {
      type: 'warning'
    })
    await subsidiaryClientApi.deleteSubsidiaryClient(row.id)
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
          await subsidiaryClientApi.updateSubsidiaryClient(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await subsidiaryClientApi.createSubsidiaryClient(submitData)
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
    client_code: '',
    client_name: '',
    client_short_name: ''
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
