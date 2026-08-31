<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>财务管理</span>
        <el-button type="primary" @click="handleAdd">新增记录</el-button>
      </div>
    </template>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-input v-model="filters.order_no" placeholder="订单号" clearable @change="fetchData" />
      </el-col>
      <el-col :span="6">
        <el-input v-model="filters.project_name" placeholder="项目名称" clearable @change="fetchData" />
      </el-col>
      <el-col :span="6">
        <el-input v-model="filters.invoice_status" placeholder="发票状态" clearable @change="fetchData" />
      </el-col>
      <el-col :span="6">
        <el-button @click="resetFilters">重置</el-button>
      </el-col>
    </el-row>

    <el-table :data="tableData" v-loading="loading" border stripe>
      <el-table-column type="index" label="#" width="55" />
      <el-table-column prop="order_no" label="订单号" width="150" />
      <el-table-column prop="client_short_name" label="客户简称" width="120" />
      <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip />
      <el-table-column prop="settlement_method" label="结账方式" width="110" />
      <el-table-column prop="total_incl_tax" label="总价含税" width="120">
        <template #default="{ row }">
          {{ toMoney(row.total_incl_tax) }}
        </template>
      </el-table-column>
      <el-table-column prop="invoice_status" label="发票状态" width="100" />
      <el-table-column prop="sales_person_name" label="销售" width="100" />
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">{{ formatDatetime(row.created_at) }}</template>
      </el-table-column>

      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <el-popover
            placement="left"
            :width="760"
            trigger="click"
            title="财务记录详情"
            @show="loadFinanceDetail(row.finance_id)"
          >
            <template #reference>
              <el-button type="info" size="small" link>
                <el-icon><View /></el-icon>
                查看详情
              </el-button>
            </template>

            <div class="detail-popover" v-loading="detailLoadingId === row.finance_id">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="财务ID" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).finance_id }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="订单号">
                  <span class="detail-value">{{ getDetailRow(row).order_no || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="项目名称">
                  <span class="detail-value">{{ getDetailRow(row).project_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ getDetailRow(row).client_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="项目状态">
                  <span class="detail-value">{{ getDetailRow(row).project_status || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="从客户接单时间" :span="2">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).customer_reception_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="销售人员">
                  <span class="detail-value">{{ getDetailRow(row).sales_person_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟单人员">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_person_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="结账方式">
                  <span class="detail-value">{{ getDetailRow(row).settlement_method || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="发票状态">
                  <span class="detail-value">{{ getDetailRow(row).invoice_status || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="单价不含税">
                  <span class="detail-value">{{ toMoney(getDetailRow(row).unit_price_excl_tax) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="单价含税">
                  <span class="detail-value">{{ toMoney(getDetailRow(row).unit_price_incl_tax) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="总价不含税">
                  <span class="detail-value">{{ toMoney(getDetailRow(row).total_excl_tax) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="总价含税">
                  <span class="detail-value">{{ toMoney(getDetailRow(row).total_incl_tax) }}</span>
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

              <template v-if="getDetailRow(row).payments?.length">
                <div class="payment-title">收款明细</div>
                <el-table :data="sortedPayments(getDetailRow(row).payments)" border size="small">
                  <el-table-column label="阶段" width="95">
                    <template #default="{ row: p }">{{ stageTypeText[p.stage_type] || p.stage_type || '-' }}</template>
                  </el-table-column>
                  <el-table-column prop="stage_no" label="期次" width="60" />
                  <el-table-column label="预定金额" width="110">
                    <template #default="{ row: p }">{{ toMoney(p.planned_amount) }}</template>
                  </el-table-column>
                  <el-table-column label="实际金额" width="110">
                    <template #default="{ row: p }">{{ toMoney(p.actual_amount) }}</template>
                  </el-table-column>
                  <el-table-column prop="payment_method" label="付款方式" width="120" />
                  <el-table-column label="付款时间" min-width="160">
                    <template #default="{ row: p }">{{ formatDatetime(p.payment_time) }}</template>
                  </el-table-column>
                  <el-table-column label="确认人" width="120">
                    <template #default="{ row: p }">{{ userNameById(p.confirmed_by) }}</template>
                  </el-table-column>
                  <el-table-column label="确认时间" min-width="160">
                    <template #default="{ row: p }">{{ formatDatetime(p.confirmed_at) }}</template>
                  </el-table-column>
                </el-table>
              </template>
            </div>
          </el-popover>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton action="edit" @click="handleEdit(row)" />
          <TableActionButton action="delete" @click="handleDelete(row)" />
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
      style="margin-top: 16px"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑财务记录' : '新增财务记录'"
      width="920px"
      @close="onDialogClose"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-divider content-position="left">关联项目</el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="选择项目" prop="project_id">
              <el-select
                v-model="form.project_id"
                filterable
                placeholder="搜索订单号或项目名称"
                style="width:100%"
                @change="onProjectSelect"
              >
                <el-option
                  v-for="p in projectList"
                  :key="p.id"
                  :label="`${p.order_no} - ${p.project_name}`"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户编号">
              <el-input v-model="form._client_code" readonly placeholder="选择项目后自动带出" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户简称">
              <el-input v-model="form._client_short_name" readonly placeholder="选择项目后自动带出" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目名称">
              <el-input v-model="form._project_name" readonly placeholder="选择项目后自动带出" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目状态">
              <el-input v-model="form._project_status" readonly placeholder="选择项目后自动带出" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="接单时间">
              <el-date-picker
                v-model="form._reception_time"
                type="datetime"
                style="width:100%"
                readonly
                placeholder="选择项目后自动带出"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">财务信息</el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="销售人员">
              <el-select v-model="form.sales_person_id" filterable clearable placeholder="请选择" style="width:100%">
                <el-option v-for="u in userList" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟单人员">
              <el-select v-model="form.follow_up_person_id" filterable clearable placeholder="请选择" style="width:100%">
                <el-option v-for="u in userList" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="结账方式">
              <el-input v-model="form.settlement_method" placeholder="如：月结/单结/预付" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发票状态">
              <el-select v-model="form.invoice_status" style="width:100%">
                <el-option label="未开" value="unissued" />
                <el-option label="部分开票" value="partial" />
                <el-option label="已开" value="issued" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="单价不含税">
              <el-input-number v-model="form.unit_price_excl_tax" :precision="2" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单价含税">
              <el-input-number v-model="form.unit_price_incl_tax" :precision="2" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="总价不含税">
              <el-input-number v-model="form.total_excl_tax" :precision="2" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="总价含税">
              <el-input-number v-model="form.total_incl_tax" :precision="2" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" :rows="2" />
        </el-form-item>

        <el-divider content-position="left">收款明细</el-divider>

        <div v-for="(p, idx) in form.payments" :key="idx" class="payment-row">
          <div class="payment-row-header">
            <span class="payment-label">第 {{ idx + 1 }} 项</span>
            <el-button type="danger" :icon="Delete" circle size="small" @click="form.payments.splice(idx, 1)" />
          </div>

          <el-row :gutter="12">
            <el-col :span="6">
              <el-form-item label="阶段" label-width="70px">
                <el-select v-model="p.stage_type" style="width:100%" @change="onStageTypeChange(p)">
                  <el-option label="定金" value="deposit" />
                  <el-option label="中期款" value="mid" />
                  <el-option label="尾款" value="final" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="期次" label-width="50px">
                <el-input-number v-model="p.stage_no" :min="1" :max="9" style="width:100%" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="7">
              <el-form-item label="预定金额" label-width="70px">
                <el-input-number v-model="p.planned_amount" :precision="2" :min="0" style="width:100%" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="7">
              <el-form-item label="实际金额" label-width="70px">
                <el-input-number v-model="p.actual_amount" :precision="2" :min="0" style="width:100%" controls-position="right" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="12">
            <el-col :span="7">
              <el-form-item label="付款时间" label-width="70px">
                <el-date-picker v-model="p.payment_time" type="datetime" style="width:100%" placeholder="选择时间" value-format="YYYY-MM-DDTHH:mm:ss" />
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item label="付款方式" label-width="70px">
                <el-input v-model="p.payment_method" placeholder="如：银行转账" />
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item label="确认人" label-width="60px">
                <el-select v-model="p.confirmed_by" filterable clearable placeholder="请选择" style="width:100%">
                  <el-option v-for="u in userList" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="7">
              <el-form-item label="确认时间" label-width="70px">
                <el-date-picker v-model="p.confirmed_at" type="datetime" style="width:100%" placeholder="选择时间" value-format="YYYY-MM-DDTHH:mm:ss" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="payment-actions">
          <el-button @click="addPayment('deposit')">+ 添加定金</el-button>
          <el-button type="primary" plain @click="addPayment('mid')">+ 添加中期款</el-button>
          <el-button type="success" plain @click="addPayment('final')">+ 添加尾款</el-button>
          <el-button type="info" plain @click="addPayment()">+ 添加默认阶段</el-button>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Delete, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useFormDraft } from '@/composables/useFormDraft'
import {
  getFinanceRecords,
  getFinanceCount,
  getFinanceRecord,
  createFinanceRecord,
  updateFinanceRecord,
  deleteFinanceRecord,
  getUsers,
  getProjects,
} from '@/api/finance'

const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const filters = reactive({ order_no: '', project_name: '', invoice_status: '' })

const userList = ref([])
const projectList = ref([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const formRef = ref(null)

const detailCache = reactive({})
const detailLoadingId = ref(null)

const stageTypeText = {
  deposit: '定金',
  mid: '中期款',
  final: '尾款',
}

const rules = {
  project_id: [{ required: true, message: '请选择关联项目', trigger: 'change' }],
}

const defaultForm = () => ({
  project_id: null,
  sales_person_id: null,
  follow_up_person_id: null,
  settlement_method: '',
  unit_price_excl_tax: null,
  unit_price_incl_tax: null,
  total_excl_tax: null,
  total_incl_tax: null,
  invoice_status: 'unissued',
  remarks: '',
  payments: [],
  _client_code: '',
  _client_short_name: '',
  _project_name: '',
  _project_status: '',
  _reception_time: null,
})

const form = reactive(defaultForm())
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({ namespace: 'finance-record', form, createDefault: defaultForm, formRef })

const toMoney = (val) => (val != null ? `￥${Number(val).toFixed(2)}` : '-')

const formatDatetime = (val) => {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { hour12: false })
}

const userNameById = (userId) => {
  if (!userId) return '-'
  const user = userList.value.find(u => u.id === userId)
  return user ? (user.full_name || user.username || '-') : '-'
}

const normalizePayment = (payment = {}) => ({
  stage_type: payment.stage_type || 'mid',
  stage_no: payment.stage_no ?? 1,
  planned_amount: payment.planned_amount ?? null,
  actual_amount: payment.actual_amount ?? null,
  payment_time: payment.payment_time || null,
  payment_method: payment.payment_method || '',
  confirmed_by: payment.confirmed_by || null,
  confirmed_at: payment.confirmed_at || null,
})

const sortedPayments = (payments = []) => {
  const stageWeight = { deposit: 1, mid: 2, final: 3 }
  return [...payments]
    .map(normalizePayment)
    .sort((a, b) => {
      const wa = stageWeight[a.stage_type] ?? 9
      const wb = stageWeight[b.stage_type] ?? 9
      if (wa !== wb) return wa - wb
      return (a.stage_no ?? 1) - (b.stage_no ?? 1)
    })
}

const getDetailRow = (row) => detailCache[row.finance_id] || row

const getNextStageNo = (stageType) => {
  if (!stageType) return 1
  if (stageType === 'deposit' || stageType === 'final') return 1
  const maxNo = form.payments
    .filter(p => p.stage_type === stageType)
    .reduce((max, p) => Math.max(max, p.stage_no || 0), 0)
  return maxNo + 1
}

const onProjectSelect = (projectId) => {
  const proj = projectList.value.find(p => p.id === projectId)
  if (!proj) return
  form._client_code = proj.client_code || ''
  form._client_short_name = proj.client_short_name || ''
  form._project_name = proj.project_name || ''
  form._project_status = proj.project_status || ''
  form._reception_time = proj.customer_reception_time || null
}

const addPayment = (stageType = 'mid') => {
  form.payments.push(normalizePayment({
    stage_type: stageType,
    stage_no: getNextStageNo(stageType),
  }))
}

const onStageTypeChange = (payment) => {
  if (!payment?.stage_type) return
  payment.stage_no = getNextStageNo(payment.stage_type)
}

const loadFinanceDetail = async (financeId) => {
  if (!financeId || detailCache[financeId]) return
  detailLoadingId.value = financeId
  try {
    const detail = await getFinanceRecord(financeId)
    detailCache[financeId] = {
      ...detail,
      payments: sortedPayments(detail.payments || []),
    }
  } catch (e) {
    ElMessage.error(e?.detail || '加载详情失败')
  } finally {
    detailLoadingId.value = null
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const skip = (pagination.page - 1) * pagination.limit
    const params = { skip, limit: pagination.limit }
    if (filters.invoice_status) params.invoice_status = filters.invoice_status
    if (filters.project_name) params.project_name = filters.project_name
    if (filters.order_no) params.order_no = filters.order_no

    const [records, countRes] = await Promise.all([
      getFinanceRecords(params),
      getFinanceCount(params),
    ])

    tableData.value = records
    pagination.total = countRes.total
  } catch (e) {
    ElMessage.error(e?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const fetchDropdowns = async () => {
  try {
    const [users, projects] = await Promise.all([
      getUsers({ limit: 500 }),
      getProjects({ limit: 500 }),
    ])
    userList.value = Array.isArray(users) ? users : (users.items || [])
    projectList.value = Array.isArray(projects) ? projects : (projects.items || [])
  } catch (_) {
    userList.value = []
    projectList.value = []
  }
}

const resetFilters = () => {
  filters.order_no = ''
  filters.project_name = ''
  filters.invoice_status = ''
  fetchData()
}

const fillFormByRecord = (record) => {
  Object.assign(form, {
    project_id: record.project_id,
    sales_person_id: record.sales_person_id || null,
    follow_up_person_id: record.follow_up_person_id || null,
    settlement_method: record.settlement_method || '',
    unit_price_excl_tax: record.unit_price_excl_tax ?? null,
    unit_price_incl_tax: record.unit_price_incl_tax ?? null,
    total_excl_tax: record.total_excl_tax ?? null,
    total_incl_tax: record.total_incl_tax ?? null,
    invoice_status: record.invoice_status || 'unissued',
    remarks: record.remarks || '',
    _client_code: '',
    _client_short_name: record.client_short_name || '',
    _project_name: record.project_name || '',
    _project_status: record.project_status || '',
    _reception_time: record.customer_reception_time || null,
  })

  const proj = projectList.value.find(p => p.id === record.project_id)
  if (proj) form._client_code = proj.client_code || ''

  form.payments = sortedPayments(record.payments || [])
}

const handleAdd = async () => {
  isEdit.value = false
  editId.value = null
  Object.assign(form, defaultForm())
  dialogVisible.value = true
  await beginDraft('create')
}

const handleEdit = async (row) => {
  isEdit.value = true
  editId.value = row.finance_id

  let source = row
  try {
    const detail = await getFinanceRecord(row.finance_id)
    source = detail
    detailCache[row.finance_id] = {
      ...detail,
      payments: sortedPayments(detail.payments || []),
    }
  } catch (_) {
    source = getDetailRow(row)
  }

  fillFormByRecord(source)
  dialogVisible.value = true
  await beginDraft(`edit:${row.finance_id}`)
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除订单 ${row.order_no || ''} 的财务记录吗？`, '警告', { type: 'warning' })
    await deleteFinanceRecord(row.finance_id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.detail || '删除失败')
  }
}

const handleSubmit = async () => {
  await formRef.value?.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const payload = {
        project_id: form.project_id,
        sales_person_id: form.sales_person_id || null,
        follow_up_person_id: form.follow_up_person_id || null,
        settlement_method: form.settlement_method || null,
        unit_price_excl_tax: form.unit_price_excl_tax,
        unit_price_incl_tax: form.unit_price_incl_tax,
        total_excl_tax: form.total_excl_tax,
        total_incl_tax: form.total_incl_tax,
        invoice_status: form.invoice_status || 'unissued',
        remarks: form.remarks || null,
        payments: sortedPayments(form.payments),
      }

      if (isEdit.value) {
        await updateFinanceRecord(editId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createFinanceRecord(payload)
        ElMessage.success('创建成功')
      }

      clearDraft()
      dialogVisible.value = false
      fetchData()
    } catch (e) {
      ElMessage.error(e?.detail || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetForm = () => {
  Object.assign(form, defaultForm())
  formRef.value?.resetFields()
}
const onDialogClose = () => { pauseDraft(); resetForm() }

onMounted(() => {
  fetchData()
  fetchDropdowns()
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

.payment-title {
  margin-top: 12px;
  margin-bottom: 8px;
  font-weight: 500;
  color: #303133;
}

.payment-row {
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px 2px;
  margin-bottom: 10px;
}

.payment-row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.payment-label {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.payment-actions {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

@media (max-width: 900px) {
  .payment-actions {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
