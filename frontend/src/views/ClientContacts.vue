<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>客户联系人及回访</span>
        <el-button type="primary" @click="handleAdd">新增回访记录</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="200" />
      <el-table-column prop="client_short_name" label="客户简称" width="150" />
      <el-table-column prop="client_manager" label="客户负责人" width="150" />
      <el-table-column prop="manager_contact" label="负责人联系方式" width="150" />
      <el-table-column prop="visit_count" label="回访次数" width="100" />
      <el-table-column prop="visit_date" label="日期" width="120" />
      <el-table-column prop="visit_type" label="回访形式" width="120" />
      <el-table-column prop="client_attitude" label="客户态度" width="120" />
      <el-table-column prop="follow_up_count" label="跟进次数" width="100" />
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
      width="900px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="140px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
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
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户名称" prop="client_name">
              <el-input v-model="form.client_name" :disabled="true" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户简称" prop="client_short_name">
              <el-input v-model="form.client_short_name" :disabled="true" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户负责人" prop="client_manager">
              <el-input v-model="form.client_manager" :disabled="true" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="负责人联系方式" prop="manager_contact">
              <el-input v-model="form.manager_contact" :disabled="true" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="回访次数" prop="visit_count">
              <el-input-number v-model="form.visit_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="日期" prop="visit_date">
              <el-date-picker
                v-model="form.visit_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="回访形式" prop="visit_type">
              <el-select v-model="form.visit_type" placeholder="请选择" style="width: 100%">
                <el-option label="电话" value="phone" />
                <el-option label="邮件" value="email" />
                <el-option label="上门" value="onsite" />
                <el-option label="视频会议" value="video" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户态度" prop="client_attitude">
              <el-select v-model="form.client_attitude" placeholder="请选择" style="width: 100%">
                <el-option label="积极" value="positive" />
                <el-option label="中性" value="neutral" />
                <el-option label="消极" value="negative" />
                <el-option label="未回应" value="no_response" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟进次数" prop="follow_up_count">
              <el-input-number v-model="form.follow_up_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="跟进时间" prop="follow_up_date">
              <el-date-picker
                v-model="form.follow_up_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="详细说明" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="跟进情况" prop="follow_up_status">
          <el-input v-model="form.follow_up_status" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="2" />
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
import * as clientContactApi from '../api/clientContacts'
import * as clientApi from '../api/clients'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增回访记录')
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
  client_short_name: '',
  client_manager: '',
  manager_contact: '',
  visit_count: 0,
  visit_date: '',
  visit_type: '',
  client_attitude: '',
  description: '',
  follow_up_count: 0,
  follow_up_date: '',
  follow_up_status: '',
  remarks: ''
})

const rules = {
  client_code: [{ required: true, message: '请选择客户编号', trigger: 'change' }],
  visit_date: [{ required: true, message: '请选择日期', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await clientContactApi.getClientContacts({
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
      form.client_manager = client.client_manager || ''
      form.manager_contact = client.manager_contact || ''
    }
  } catch (error) {
    console.error('获取客户信息失败', error)
  }
}

const handleAdd = async () => {
  dialogTitle.value = '新增回访记录'
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
  dialogTitle.value = '编辑回访记录'
  Object.assign(form, {
    id: row.id,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    client_manager: row.client_manager || '',
    manager_contact: row.manager_contact || '',
    visit_count: row.visit_count || 0,
    visit_date: row.visit_date || '',
    visit_type: row.visit_type || '',
    client_attitude: row.client_attitude || '',
    description: row.description || '',
    follow_up_count: row.follow_up_count || 0,
    follow_up_date: row.follow_up_date || '',
    follow_up_status: row.follow_up_status || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该回访记录吗？', '提示', {
      type: 'warning'
    })
    await clientContactApi.deleteClientContact(row.id)
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
          await clientContactApi.updateClientContact(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await clientContactApi.createClientContact(submitData)
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
    client_short_name: '',
    client_manager: '',
    manager_contact: '',
    visit_count: 0,
    visit_date: '',
    visit_type: '',
    client_attitude: '',
    description: '',
    follow_up_count: 0,
    follow_up_date: '',
    follow_up_status: '',
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
