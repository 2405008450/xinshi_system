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
      <el-table-column prop="consultation_code" label="咨询编号" width="160" />
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="200" show-overflow-tooltip />
      <el-table-column prop="client_short_name" label="客户简称" width="150" />
      <el-table-column prop="consultation_time" label="咨询时间" width="180">
        <template #default="{ row }">{{ formatDatetime(row.consultation_time) }}</template>
      </el-table-column>
      <el-table-column prop="consultation_method" label="咨询方式" width="120" />
      <el-table-column prop="client_source" label="客户来源" width="120" />
      <el-table-column prop="source_keyword" label="来源关键词" width="150" />
      <el-table-column prop="status" label="咨询状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="consultation_type" label="咨询类型" width="120" />

      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <el-popover
            placement="left"
            :width="760"
            trigger="click"
            title="咨询详情"
            @show="loadConsultationDetail(row.id)"
          >
            <template #reference>
              <el-button type="info" size="small" link>
                查看详情
              </el-button>
            </template>
            <div class="detail-popover" v-loading="detailLoadingId === row.id">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="ID" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询编号">
                  <span class="detail-value">{{ getDetailRow(row).consultation_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户ID">
                  <span class="detail-value">{{ getDetailRow(row).client_id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户编号">
                  <span class="detail-value">{{ getDetailRow(row).client_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户名称">
                  <span class="detail-value">{{ getDetailRow(row).client_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ getDetailRow(row).client_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).consultation_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询方式">
                  <span class="detail-value">{{ getDetailRow(row).consultation_method || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户来源">
                  <span class="detail-value">{{ getDetailRow(row).client_source || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="来源关键词">
                  <span class="detail-value">{{ getDetailRow(row).source_keyword || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询状态">
                  <span class="detail-value">{{ getStatusText(getDetailRow(row).status) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询类型">
                  <span class="detail-value">{{ getDetailRow(row).consultation_type || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="处理方式">
                  <span class="detail-value">{{ getDetailRow(row).handling_method || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客服人员ID">
                  <span class="detail-value">{{ getDetailRow(row).customer_service_id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="销售人员ID">
                  <span class="detail-value">{{ getDetailRow(row).sales_person_id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="编辑人ID">
                  <span class="detail-value">{{ getDetailRow(row).editor_id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进次数">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_count ?? 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).follow_up_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进状态">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_status || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进人ID">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_person_id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询描述" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).consultation_description || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进备注" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_remarks || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="备注" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).remarks || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).created_at) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="更新时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).updated_at) }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="160" fixed="right">
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
      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户编号" prop="client_code">
              <el-select
                v-model="form.client_code"
                filterable
                placeholder="请选择客户编号"
                style="width: 100%"
                @change="handleClientChange"
              >
                <el-option
                  v-for="client in clientOptions"
                  :key="client.id"
                  :label="`${client.client_code} - ${client.client_name}`"
                  :value="client.client_code"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户名称">
              <el-input v-model="form.client_name" disabled />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户简称">
              <el-input v-model="form.client_short_name" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="咨询时间" prop="consultation_time">
              <el-date-picker
                v-model="form.consultation_time"
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
            <el-form-item label="咨询状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择" style="width: 100%">
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
            <el-form-item label="处理方式" prop="handling_method">
              <el-input v-model="form.handling_method" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="跟进次数" prop="follow_up_count">
              <el-input-number v-model="form.follow_up_count" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟进时间" prop="follow_up_time">
              <el-date-picker
                v-model="form.follow_up_time"
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
            <el-form-item label="跟进状态" prop="follow_up_status">
              <el-input v-model="form.follow_up_status" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟进人ID" prop="follow_up_person_id">
              <el-input v-model="form.follow_up_person_id" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="咨询描述" prop="consultation_description">
          <el-input v-model="form.consultation_description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="跟进备注" prop="follow_up_remarks">
          <el-input v-model="form.follow_up_remarks" type="textarea" :rows="2" />
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
const detailCache = reactive({})
const detailLoadingId = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0,
})

const defaultForm = () => ({
  id: null,
  client_id: null,
  client_code: '',
  client_name: '',
  client_short_name: '',
  consultation_time: '',
  consultation_method: '',
  client_source: '',
  source_keyword: '',
  consultation_description: '',
  status: 'pending',
  consultation_type: '',
  handling_method: '',
  remarks: '',
  customer_service_id: '',
  sales_person_id: '',
  editor_id: '',
  follow_up_count: 0,
  follow_up_time: '',
  follow_up_status: '',
  follow_up_remarks: '',
  follow_up_person_id: '',
})

const form = reactive(defaultForm())

const rules = {
  client_code: [{ required: true, message: '请选择客户编号', trigger: 'change' }],
  consultation_time: [{ required: true, message: '请选择咨询时间', trigger: 'change' }],
}

const getStatusType = (status) => {
  const statusMap = {
    pending: 'info',
    processing: 'warning',
    converted: 'success',
    abandoned: 'danger',
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusMap = {
    pending: '待处理',
    processing: '处理中',
    converted: '已转化',
    abandoned: '已放弃',
  }
  return statusMap[status] || status || '-'
}

const formatDatetime = (val) => {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { hour12: false })
}

const getDetailRow = (row) => detailCache[row.id] || row

const loadClients = async () => {
  try {
    const res = await clientApi.getClients({ skip: 0, limit: 500 })
    clientOptions.value = Array.isArray(res) ? res : []
  } catch {
    clientOptions.value = []
  }
}

const enrichClientFields = (row) => {
  if (row.client_code && row.client_name && row.client_short_name) return row
  const matched = clientOptions.value.find((c) => c.id === row.client_id)
  if (!matched) return row
  return {
    ...row,
    client_code: row.client_code || matched.client_code || '',
    client_name: row.client_name || matched.client_name || '',
    client_short_name: row.client_short_name || matched.client_short_name || '',
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await consultationApi.getConsultations({
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    })
    const list = Array.isArray(res) ? res.map(enrichClientFields) : []
    tableData.value = list
    pagination.total = list.length
  } catch {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const handleClientChange = (clientCode) => {
  const client = clientOptions.value.find((c) => c.client_code === clientCode)
  if (!client) {
    form.client_id = null
    form.client_name = ''
    form.client_short_name = ''
    return
  }
  form.client_id = client.id || null
  form.client_name = client.client_name || ''
  form.client_short_name = client.client_short_name || ''
}

const toNullable = (v) => (v === '' ? null : v)

const buildPayload = () => ({
  client_id: form.client_id,
  consultation_time: toNullable(form.consultation_time),
  consultation_method: toNullable(form.consultation_method),
  client_source: toNullable(form.client_source),
  source_keyword: toNullable(form.source_keyword),
  consultation_description: toNullable(form.consultation_description),
  remarks: toNullable(form.remarks),
  customer_service_id: toNullable(form.customer_service_id),
  sales_person_id: toNullable(form.sales_person_id),
  status: toNullable(form.status),
  consultation_type: toNullable(form.consultation_type),
  handling_method: toNullable(form.handling_method),
  editor_id: toNullable(form.editor_id),
  follow_up_count: form.follow_up_count ?? 0,
  follow_up_time: toNullable(form.follow_up_time),
  follow_up_status: toNullable(form.follow_up_status),
  follow_up_remarks: toNullable(form.follow_up_remarks),
  follow_up_person_id: toNullable(form.follow_up_person_id),
})

const loadConsultationDetail = async (id) => {
  if (!id || detailCache[id]) return
  detailLoadingId.value = id
  try {
    const detail = await consultationApi.getConsultation(id)
    detailCache[id] = enrichClientFields(detail)
  } catch {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoadingId.value = null
  }
}

const handleAdd = async () => {
  dialogTitle.value = '新增咨询'
  resetForm()
  dialogVisible.value = true
}

const fillFormByRow = (row) => {
  const item = enrichClientFields(row)
  Object.assign(form, {
    id: item.id,
    client_id: item.client_id || null,
    client_code: item.client_code || '',
    client_name: item.client_name || '',
    client_short_name: item.client_short_name || '',
    consultation_time: item.consultation_time || '',
    consultation_method: item.consultation_method || '',
    client_source: item.client_source || '',
    source_keyword: item.source_keyword || '',
    consultation_description: item.consultation_description || '',
    status: item.status || 'pending',
    consultation_type: item.consultation_type || '',
    handling_method: item.handling_method || '',
    remarks: item.remarks || '',
    customer_service_id: item.customer_service_id || '',
    sales_person_id: item.sales_person_id || '',
    editor_id: item.editor_id || '',
    follow_up_count: item.follow_up_count ?? 0,
    follow_up_time: item.follow_up_time || '',
    follow_up_status: item.follow_up_status || '',
    follow_up_remarks: item.follow_up_remarks || '',
    follow_up_person_id: item.follow_up_person_id || '',
  })
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑咨询'
  try {
    const detail = await consultationApi.getConsultation(row.id)
    detailCache[row.id] = enrichClientFields(detail)
    fillFormByRow(detailCache[row.id])
  } catch {
    fillFormByRow(row)
  }
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该咨询记录吗？', '提示', { type: 'warning' })
    await consultationApi.deleteConsultation(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const payload = buildPayload()
      if (form.id) {
        await consultationApi.updateConsultation(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await consultationApi.createConsultation(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (error) {
      ElMessage.error(error.detail || '操作失败')
    }
  })
}

const resetForm = () => {
  Object.assign(form, defaultForm())
  formRef.value?.resetFields()
}

onMounted(async () => {
  await loadClients()
  await fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-popover {
  max-height: 560px;
  overflow-y: auto;
}

.detail-value {
  word-break: break-all;
  color: #606266;
  font-size: 13px;
}
</style>
