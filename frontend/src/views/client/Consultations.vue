<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>咨询基本情况</span>
        <el-button type="primary" @click="handleAdd">新增咨询</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="200" />
      <el-table-column prop="client_short_name" label="客户简称" width="150" />
      <el-table-column prop="consultation_date" label="咨询时间" width="180" />
      <el-table-column prop="consultation_method" label="咨询方式" width="120" />
      <el-table-column prop="client_source" label="客户来源" width="120" />
      <el-table-column prop="source_keyword" label="来源关键词" width="150" />
      <el-table-column prop="consultation_status" label="咨询状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.consultation_status)">
            {{ getStatusText(row.consultation_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="consultation_type" label="咨询类型" width="120" />
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
            <el-form-item label="咨询时间" prop="consultation_date">
              <el-date-picker
                v-model="form.consultation_date"
                type="datetime"
                placeholder="选择日期时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="咨询方式" prop="consultation_method">
              <el-select v-model="form.consultation_method" placeholder="请选择" style="width: 100%">
                <el-option label="电话" value="phone" />
                <el-option label="邮件" value="email" />
                <el-option label="在线咨询" value="online" />
                <el-option label="上门" value="onsite" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户来源" prop="client_source">
              <el-select v-model="form.client_source" placeholder="请选择" style="width: 100%">
                <el-option label="官网" value="website" />
                <el-option label="搜索引擎" value="search_engine" />
                <el-option label="推荐" value="referral" />
                <el-option label="社交媒体" value="social_media" />
                <el-option label="展会" value="exhibition" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="来源关键词" prop="source_keyword">
              <el-input v-model="form.source_keyword" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="咨询状态" prop="consultation_status">
              <el-select v-model="form.consultation_status" placeholder="请选择" style="width: 100%">
                <el-option label="待处理" value="pending" />
                <el-option label="处理中" value="processing" />
                <el-option label="已转化" value="converted" />
                <el-option label="已放弃" value="abandoned" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="咨询类型" prop="consultation_type">
              <el-select v-model="form.consultation_type" placeholder="请选择" style="width: 100%">
                <el-option label="价格咨询" value="price" />
                <el-option label="服务咨询" value="service" />
                <el-option label="技术咨询" value="technical" />
                <el-option label="合作咨询" value="cooperation" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客服人员" prop="service_staff">
              <el-input v-model="form.service_staff" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="销售人员" prop="sales_staff">
              <el-input v-model="form.sales_staff" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="咨询描述" prop="consultation_description">
          <el-input v-model="form.consultation_description" type="textarea" :rows="4" />
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
import * as consultationApi from '@/api/consultations'
import * as clientApi from '@/api/clients'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增咨询')
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
  consultation_date: '',
  consultation_method: '',
  client_source: '',
  source_keyword: '',
  consultation_description: '',
  service_staff: '',
  sales_staff: '',
  consultation_status: 'pending',
  consultation_type: '',
  remarks: ''
})

const rules = {
  client_code: [{ required: true, message: '请选择客户编号', trigger: 'change' }],
  consultation_date: [{ required: true, message: '请选择咨询时间', trigger: 'change' }]
}

const getStatusType = (status) => {
  const statusMap = {
    pending: 'info',
    processing: 'warning',
    converted: 'success',
    abandoned: 'danger'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusMap = {
    pending: '待处理',
    processing: '处理中',
    converted: '已转化',
    abandoned: '已放弃'
  }
  return statusMap[status] || status
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await consultationApi.getConsultations({
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
  dialogTitle.value = '新增咨询'
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
  dialogTitle.value = '编辑咨询'
  Object.assign(form, {
    id: row.id,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    consultation_date: row.consultation_date || '',
    consultation_method: row.consultation_method || '',
    client_source: row.client_source || '',
    source_keyword: row.source_keyword || '',
    consultation_description: row.consultation_description || '',
    service_staff: row.service_staff || '',
    sales_staff: row.sales_staff || '',
    consultation_status: row.consultation_status || 'pending',
    consultation_type: row.consultation_type || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该咨询记录吗？', '提示', {
      type: 'warning'
    })
    await consultationApi.deleteConsultation(row.id)
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
          await consultationApi.updateConsultation(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await consultationApi.createConsultation(submitData)
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
    consultation_date: '',
    consultation_method: '',
    client_source: '',
    source_keyword: '',
    consultation_description: '',
    service_staff: '',
    sales_staff: '',
    consultation_status: 'pending',
    consultation_type: '',
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
