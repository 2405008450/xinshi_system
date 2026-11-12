<template>
  <DraggableFormDialog :model-value="true" :title="requestId ? '开票需求' : '发送开票需求'" append-to-body
    class="invoice-workflow-dialog" width="min(920px, calc(100vw - 32px))" top="5vh"
    :close-on-click-modal="false" :before-close="close">
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="preview">
        <AppForm :model="form" label-position="top">
          <div class="invoice-request-fields">
            <el-form-item label="发票类型">
              <el-select v-model="form.type" placeholder="请选择" @change="form.rate = null">
                <el-option v-for="item in types" :key="item.value" v-bind="item" />
              </el-select>
            </el-form-item>
            <el-form-item label="开票主体">
              <el-select v-model="form.subject" placeholder="请选择" @change="form.rate = null">
                <el-option v-for="subject in preview.subjects" :key="subject.key" :value="subject.key" :label="subjectNames[subject.key]" />
              </el-select>
              <span class="invoice-subject-hint">尽量选用税率较低的上海分公司或深圳分公司。</span>
            </el-form-item>
            <el-form-item v-if="special" label="专票税率">
              <el-select v-model="form.rate" :disabled="!form.subject" placeholder="请选择">
                <el-option v-for="rate in availableRates" :key="rate" :value="rate" :label="rate + '%'" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="说明"><el-input v-model="form.note" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
        </AppForm>
        <p>接收人：{{ preview.recipients.map(person => person.name).join('、') || '请在财务设置中选择接收人' }}</p>
        <el-collapse>
          <el-collapse-item title="查看三个开票主体的资料" name="subjects">
            <el-descriptions v-for="subject in preview.subjects" :key="subject.key" :title="subject.name" :column="2" border size="small">
              <el-descriptions-item v-for="field in invoicePartyFields" :key="field.key" :label="field.label">{{ subject.party[field.key] || '待填写' }}</el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>
      </template>
      <template v-if="request">
        <p>{{ request.snapshot.sender }} → {{ request.snapshot.recipient_names?.join('、') }}</p>
        <p>{{ request.snapshot.invoice_type }}{{ request.snapshot.tax_rate ? ' · ' + request.snapshot.tax_rate + '%' : '' }} · {{ request.snapshot.subject?.name }}</p>
        <p v-if="request.snapshot.note" class="invoice-request-note">说明：{{ request.snapshot.note }}</p>
        <p v-if="receivedNames">已确认收到需求：{{ receivedNames }}</p>
        <el-button v-if="request.is_recipient && !received" :loading="busy" @click="receipt()">发送需求收到回执</el-button>
        <el-collapse v-if="request.snapshot.subject">
          <el-collapse-item title="查看本次开票主体资料" name="subject">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item v-for="field in invoicePartyFields" :key="field.key" :label="field.label">{{ request.snapshot.subject.party?.[field.key] || '待填写' }}</el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>
      </template>
      <section v-for="group in customerGroups" :key="group.client_id" class="invoice-customer-group">
        <header class="invoice-customer-heading">
          <h3>{{ group.customer.client_name }}</h3>
          <span>本次开票金额 <strong>{{ amountText(group.totals) }}</strong></span>
        </header>
        <el-collapse>
          <el-collapse-item title="客户开票信息" :name="group.client_id">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item v-for="field in invoicePartyFields" :key="field.key" :label="field.label">{{ group.customer.client_party?.[field.key] || '待填写' }}</el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>
        <el-table :data="group.projects" row-key="project_id">
          <el-table-column prop="order_no" label="订单号" min-width="150" />
          <el-table-column prop="project_name" label="项目" min-width="180" />
          <el-table-column label="项目含税金额" min-width="145">
            <template #default="{row}">{{ amountText(row.totals) }}</template>
          </el-table-column>
          <el-table-column v-if="request" label="操作" min-width="190">
            <template #default="{row}">
              <el-button v-if="request.is_recipient || delivery(row)" link type="primary" @click="openInvoice(row)">发票</el-button>
              <template v-if="delivery(row)">
                <span v-if="delivery(row).receipt">已回执</span>
                <el-button v-else-if="request.is_sender" link type="primary" :loading="busy" @click="receipt(row.project_id)">发送发票收到回执</el-button>
                <span v-else>已发送</span>
                <ScreenshotText :text="delivery(row).proofs" :show-text="false" />
              </template>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="close()">关闭</el-button>
      <el-button v-if="preview" type="primary" :loading="busy" :disabled="!canSend" @click="send">发送开票需求</el-button>
    </template>
  </DraggableFormDialog>
  <ProjectInvoiceDialog v-if="invoiceProject" :model-value="true" :request-id="requestId"
    :context="invoiceContext" :can-deliver="request.is_recipient && received && !delivery(invoiceProject)"
    @update:model-value="invoiceProject = null" @saved="load" />
</template>

<script setup>
import {computed, onMounted, reactive, ref} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {invoicePartyFields} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
import ScreenshotText from './ScreenshotText.vue'

const props = defineProps({projectIds:{type:Array,default:()=>[]}, requestId:String})
const emit = defineEmits(['close','sent'])
const preview = ref(), request = ref(), loading = ref(false), busy = ref(false), error = ref('')
const invoiceProject = ref()
const invoiceContext = computed(() => ({projectId:invoiceProject.value?.project_id,
  preview:{totals:invoiceProject.value?.totals, required:true}}))
const form = reactive({type:'electronic_normal', subject:'', rate:null, note:''})
let previousSubmission, submissionKey
const types = [
  {value:'electronic_special',label:'电子专票'}, {value:'electronic_normal',label:'电子普票'},
  {value:'paper_special',label:'纸质专票'}, {value:'paper_normal',label:'纸质普票'},
]
const subjectNames = {guangzhou:'广州总公司',shenzhen:'深圳分公司',shanghai:'上海分公司'}
const special = computed(() => form.type.endsWith('_special'))
const availableRates = computed(() => form.subject === 'guangzhou' ? [6] : [1,3])
const canSend = computed(() => !loading.value && form.type && form.subject && (!special.value || form.rate) && preview.value?.recipients.length)
const projects = computed(() => {
  const snapshot = request.value?.snapshot
  return preview.value?.projects || snapshot?.projects || (snapshot ? [{...snapshot,
    project_id:request.value.project_id, client_id:request.value.client_id}] : [])
})
const customerGroups = computed(() => {
  const byId = new Map(projects.value.map(project => [project.project_id, project]))
  const groups = preview.value?.customer_groups || request.value?.customer_groups || []
  return groups.map(group => {
    const rows = group.project_ids.map(id => byId.get(id))
    return {...group, customer:rows[0], projects:rows}
  })
})
const received = computed(() => Boolean(request.value?.snapshot.request_receipts?.[localStorage.getItem('user_id')]))
const receivedNames = computed(() => Object.values(request.value?.snapshot.request_receipts || {}).map(item => item.name).join('、'))
const amountText = totals => Object.entries(totals || {}).map(([currency, amount]) => `${currency} ${amount}`).join('；') || '—'
const delivery = row => request.value?.snapshot.deliveries?.[row.project_id]
const openInvoice = row => { invoiceProject.value = row }

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (props.requestId) {
      request.value = await api.get(`/invoice-workflow/requests/${props.requestId}`)
    } else {
      preview.value = await api.post('/invoice-workflow/requests/preview', {project_ids:props.projectIds}, {timeout:60000})
      const defaults = new Set(preview.value.projects.map(row => row.default_subject))
      if (defaults.size === 1) form.subject = preview.value.projects[0].default_subject || ''
    }
  } catch (e) { error.value = getLocalizedErrorMessage(e, '加载开票需求失败') }
  finally { loading.value = false }
}
async function send() {
  if (busy.value || !canSend.value) return
  const data = {project_ids:props.projectIds, invoice_type:form.type, subject_key:form.subject, tax_rate:form.rate,
    note:form.note, settings_revision:preview.value.settings_revision,
    expected_user_ids:preview.value.recipients.map(person => person.id)}
  const signature = JSON.stringify(data)
  if (signature !== previousSubmission) {
    previousSubmission = signature
    submissionKey = crypto.randomUUID()
  }
  busy.value = true
  error.value = ''
  try {
    await api.post('/invoice-workflow/requests/batch', {...data,idempotency_key:submissionKey}, {timeout:60000})
    ElMessage.success('开票需求已发送')
    emit('sent')
    emit('close')
  } catch (e) { error.value = getLocalizedErrorMessage(e, '开票需求发送失败') }
  finally { busy.value = false }
}
async function receipt(projectId) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    request.value = await api.post(`/invoice-workflow/requests/${props.requestId}/receipts`, {project_id:projectId})
    ElMessage.success('收到回执已发送')
  } catch (e) { error.value = getLocalizedErrorMessage(e, '回执发送失败') }
  finally { busy.value = false }
}
function close(done) {
  if (busy.value) return
  if (typeof done === 'function') done()
  emit('close')
}
onMounted(load)
</script>

<style scoped>
.invoice-request-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.invoice-subject-hint { flex-basis: 100%; margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.invoice-request-note { white-space: pre-wrap; overflow-wrap: anywhere; }
.invoice-customer-group { margin-top: 16px; border: 1px solid var(--el-border-color-light); border-radius: 6px; padding: 12px; }
.invoice-customer-heading { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px 16px; margin-bottom: 8px; }
.invoice-customer-heading h3 { margin: 0; }
.el-descriptions + .el-descriptions { margin-top: 16px; }
:global(.invoice-workflow-dialog) { display:flex; flex-direction:column; max-height:90vh; overflow:hidden; }
:global(.invoice-workflow-dialog > .el-dialog__body) { flex:1; min-height:0; overflow:auto; }
:global(.invoice-workflow-dialog > .el-dialog__header),
:global(.invoice-workflow-dialog > .el-dialog__footer) { flex:none; }
</style>
