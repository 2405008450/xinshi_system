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
                <el-option v-for="(label,key) in invoiceTypeLabels" :key="key" :value="key" :label="label" />
              </el-select>
            </el-form-item>
            <el-form-item label="开票主体">
              <el-select v-model="form.subject" placeholder="请选择" @change="form.rate = null">
                <el-option v-for="subject in preview.subjects" :key="subject.key" :value="subject.key" :label="subjectNames[subject.key]" />
              </el-select>
              <span class="invoice-subject-hint">优先使用订单已保存的选择，其次采用客户默认设置或对账单主体。</span>
            </el-form-item>
            <el-form-item v-if="special" label="专票税率">
              <ReadonlyField v-if="form.subject==='guangzhou'" model-value="6%" source="auto" />
              <el-select v-else v-model="form.rate" :disabled="!form.subject" placeholder="请选择">
                <el-option v-for="rate in [1,3]" :key="rate" :value="rate" :label="rate + '%'" />
              </el-select>
            </el-form-item>
          </div>
          <div class="invoice-request-note-row">
            <el-form-item label="说明" class="invoice-request-note-field">
              <el-input v-model="form.note" type="textarea" :rows="3" maxlength="2000" show-word-limit />
            </el-form-item>
            <el-form-item label="接收人" class="invoice-request-recipient">
              {{ preview.recipients.map(person => person.name).join('、') || '请在财务设置中选择接收人' }}
            </el-form-item>
          </div>
        </AppForm>
        <el-alert v-if="mixedSelection" title="所选订单的开票主体或票种不同，请确认本次使用的统一选项。" type="warning" :closable="false" />
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
      <section v-for="group in customerGroups" :key="group.group_id || group.client_id" class="invoice-customer-group">
        <header class="invoice-customer-heading">
          <h3>{{ [group.customer.client_name,group.customer.sub_client_name,group.customer.sub_client_code].filter(Boolean).join(' · ') }}</h3>
          <span>本次开票金额 <strong>{{ amountText(group.totals) }}</strong></span>
        </header>
        <el-collapse>
          <el-collapse-item title="客户开票信息" :name="group.client_id"><el-select v-if="preview&&group.customer.client_party_options?.length>1" :model-value="partyChoices[group.client_id]||0" @change="index=>selectParty(group,index)"><el-option v-for="(party,index) in group.customer.client_party_options" :key="index" :value="index" :label="party.title||`开票信息 ${index+1}`" /></el-select>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item v-for="field in invoicePartyFields" :key="field.key" :label="field.label">{{ group.customer.client_party?.[field.key] || '待填写' }}</el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>
        <div v-if="preview" class="invoice-selection-settings">
          <span>客户默认：{{subjectNames[group.customer.client_invoice_subject]||'主体未设置'}} · {{invoiceTypeLabels[group.customer.invoice_selection?.client_invoice_type]||'电子普票'}}</span>
          <el-button link type="primary" @click="openClientInvoiceSettings(group.client_id)">查看客户管理开票设置</el-button>
        </div>
        <div v-if="!invoiceStatements.length&&combinedGroup(group)" class="invoice-combined-actions">
          <h4>多单合并结款（发票）项目</h4>
          <template v-if="request">
            <el-button v-if="request.is_recipient || availableProof(group.customer)" link type="primary"
              @click="openInvoice(group.customer,group)">合并发票</el-button>
            <template v-if="delivery(group.customer)">
              <span v-if="delivery(group.customer).receipt">已回执</span>
              <el-button v-else-if="request.is_sender" link type="primary" :loading="busy" @click="receipt(group.customer.project_id)">发送发票收到回执</el-button>
              <span v-else>已发送</span>
            </template>
            <span v-else-if="!availableProof(group.customer)&&!request.is_recipient">待上传发票</span>
          </template>
        </div>
        <el-table v-if="!invoiceStatements.length" :data="group.projects" row-key="project_id">
          <el-table-column prop="order_no" label="订单号" min-width="150" />
          <el-table-column prop="project_name" label="项目" min-width="180" />
          <el-table-column v-if="preview" label="订单开票选择" min-width="170">
            <template #default="{row}">{{subjectNames[row.invoice_selection?.subject_key]||'主体未设置'}} · {{invoiceTypeLabels[row.invoice_selection?.invoice_type]||'电子普票'}}</template>
          </el-table-column>
          <el-table-column label="项目含税金额" min-width="145">
            <template #default="{row}">{{ amountText(row.totals) }}<OrderPriceDetails :order="row.price_details" side="incl" /></template>
          </el-table-column>
          <el-table-column v-if="request&&!combinedGroup(group)" label="操作" min-width="190">
            <template #default="{row}">
              <el-button v-if="request.is_recipient || availableProof(row)" link type="primary" @click="openInvoice(row)">发票</el-button>
              <template v-if="delivery(row)">
                <span v-if="delivery(row).receipt">已回执</span>
                <el-button v-else-if="request.is_sender" link type="primary" :loading="busy" @click="receipt(row.project_id)">发送发票收到回执</el-button>
                <span v-else>已发送</span>
                <ScreenshotText :text="delivery(row).proofs" :show-text="false" invoice-drag :invoice-order-no="row.order_no" />
              </template>
            </template>
          </el-table-column>
        </el-table>
      </section>
      <section v-for="document in invoiceStatements" :key="document.board_id"><el-button v-if="request" link type="primary" @click="statementInvoice=document">发票</el-button><details><summary>{{document.statement.statement_number||document.name}} · {{amountText(document.totals)}} · {{subjectNames[document.subject_key]||'开票主体待选择'}}</summary><div class="invoice-statement-scroll"><CustomerStatementPaper :statement="document.statement" /></div></details></section>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="close()">关闭</el-button>
      <el-button v-if="preview&&!statementRefs.length" :loading="busy" :disabled="!canSaveSelection" @click="saveSelection">保存订单开票选择</el-button>
      <el-button v-if="preview" type="primary" :loading="busy" :disabled="!canSend" @click="send">发送开票需求</el-button>
    </template>
  </DraggableFormDialog>
  <SpecialStatementInvoices v-if="statementInvoice" editor-only :invoice-client-id="statementInvoice.client_id" :focus-board-id="statementInvoice.board_id" :read-only="!request?.is_recipient" @close="statementInvoice=null" @saved="load" />
  <ProjectInvoiceDialog v-if="invoiceProject" :model-value="true" :request-id="requestId"
    :context="invoiceContext" :special="!!invoiceProject.root_id" :can-deliver="request.is_recipient && received"
    @update:model-value="invoiceProject = null" @saved="load" />
</template>

<script setup>
import {computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {invoicePartyFields,invoiceTypeLabels,invoiceSubjectLabels as subjectNames,saveOrderInvoiceSelections,connectInvoiceParties,notifyInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import {clientManagementTarget} from '@/utils/clientManagementWindow'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import DraggableFormDialog from './DraggableFormDialog.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import AppForm from './AppForm.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
import ScreenshotText from './ScreenshotText.vue'
import ReadonlyField from './ReadonlyField.vue'

const props = defineProps({projectIds:{type:Array,default:()=>[]}, requestId:String, mergedSettlement:Boolean, specialSettlement:Boolean,statementRefs:{type:Array,default:()=>[]}})
const settlementScope=computed(()=>props.specialSettlement?'special':undefined)
const emit = defineEmits(['close','sent'])
const preview = ref(), request = ref(), loading = ref(false), busy = ref(false), error = ref('')
const SpecialStatementInvoices=defineAsyncComponent(()=>import('./SpecialStatementInvoices.vue'))
const statementInvoice=ref(null)
const partyChoices=reactive({})
function selectParty(group,index){partyChoices[group.client_id]=index;for(const row of preview.value.projects)if(row.client_id===group.client_id)row.client_party=row.client_party_options[index]}
const invoiceStatements=computed(()=>preview.value?.statements||request.value?.snapshot?.statements||[])
const invoiceProject = ref()
const invoiceGroup = ref()
const invoiceContext = computed(() => ({projectId:invoiceProject.value?.project_id,
  merged:!!invoiceGroup.value, preview:{totals:invoiceGroup.value?.totals||invoiceProject.value?.totals, required:true}}))
const form = reactive({type:'electronic_normal', subject:'', rate:null, note:''})
let previousSubmission, submissionKey, loadedSelection=''
let loadingSequence=0
const eventSource=`invoice-selection-${Math.random()}`
const special = computed(() => form.type.endsWith('_special'))
const taxRate=computed(()=>special.value?(form.subject==='guangzhou'?6:form.rate):null)
const canSaveSelection=computed(()=>!loading.value&&!!form.type&&!!form.subject)
const canSend = computed(() => canSaveSelection.value && (!special.value || taxRate.value) && preview.value?.recipients.length)
const mixedSelection=computed(()=>{
  const rows=preview.value?.projects||[]
  return new Set(rows.map(row=>row.default_subject)).size>1||new Set(rows.map(row=>row.invoice_selection?.invoice_type)).size>1
})
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
const availableProof = row => delivery(row)?.proofs || request.value?.snapshot.uploaded_invoices?.[row.project_id]?.proofs
function combinedGroup(group){
  return (group.projects.length>1 || preview.value&&props.mergedSettlement) &&
    !group.projects.some(row=>delivery(row)&&!delivery(row).combined_invoice_id)
}
function openInvoice(row,group){
  invoiceGroup.value=group
  invoiceProject.value=row
}

const selectionSignature=()=>JSON.stringify([form.subject,form.type,form.rate])
function openClientInvoiceSettings(id){clientManagementTarget.value={client_id:id,financeSection:'invoice'}}
function publishSelections(){
  for(const id of new Set(preview.value.projects.map(row=>row.client_id))){
    notifyInvoiceParties({kind:'records',clientId:id,source:eventSource})
  }
}
function changed(event){
  if(request.value&&!busy.value&&event.detail?.requestId===props.requestId){
    void load()
    return
  }
  if(preview.value&&!busy.value&&event.detail?.source!==eventSource&&preview.value.projects.some(row=>row.client_id===event.detail?.clientId)){
    void load({preserveSelection:selectionSignature()!==loadedSelection})
  }
}
async function load({preserveSelection=false}={}) {
  const sequence=++loadingSequence
  const initialSelection=selectionSignature()
  loading.value = true
  error.value = ''
  try {
    if (props.requestId) {
      const result=await api.get(`/invoice-workflow/requests/${props.requestId}`)
      if(sequence===loadingSequence)request.value=result
    } else {
      const result=await api.post('/invoice-workflow/requests/preview', {project_ids:props.projectIds,statement_refs:props.statementRefs,settlement_scope:settlementScope.value}, {timeout:60000})
      if(sequence!==loadingSequence)return
      preview.value=result
      if(!preserveSelection&&selectionSignature()===initialSelection){
        const subjects=new Set(preview.value.projects.map(row=>row.default_subject))
        const types=new Set(preview.value.projects.map(row=>row.invoice_selection?.invoice_type||'electronic_normal'))
        form.subject=subjects.size===1?preview.value.projects[0].default_subject||'':''
        form.type=types.size===1?[...types][0]:''
        form.rate=null
        loadedSelection=selectionSignature()
      }
    }
  } catch (e) {
    if(sequence===loadingSequence)error.value=getLocalizedErrorMessage(e,'加载开票需求失败')
  } finally {
    if(sequence===loadingSequence)loading.value=false
  }
}
async function saveSelection(){
  if(busy.value||!canSaveSelection.value)return
  busy.value=true
  error.value=''
  try{
    await saveOrderInvoiceSelections(preview.value.projects.map(row=>({
      project_id:row.project_id,revision:row.invoice_selection?.revision??0,
      subject_key:form.subject,invoice_type:form.type,
    })),settlementScope.value)
    publishSelections()
    await load({preserveSelection:true})
    loadedSelection=selectionSignature()
    ElMessage.success('订单开票选择已保存')
  }catch(e){error.value=getLocalizedErrorMessage(e,'保存订单开票选择失败')}
  finally{busy.value=false}
}
async function send() {
  if (busy.value || !canSend.value) return
  const data = {project_ids:props.projectIds,statement_refs:props.statementRefs, settlement_scope:settlementScope.value, invoice_type:form.type, subject_key:form.subject, tax_rate:taxRate.value,
    client_party_choices:partyChoices,selection_revisions:props.statementRefs.length?undefined:Object.fromEntries(preview.value.projects.map(row=>[row.project_id,row.invoice_selection?.revision??0])),
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
    publishSelections()
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
onMounted(()=>{void load();connectInvoiceParties();window.addEventListener(invoicePartiesEvent,changed)})
onBeforeUnmount(()=>{loadingSequence++;window.removeEventListener(invoicePartiesEvent,changed)})
</script>

<style scoped>
.invoice-request-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.invoice-request-note-row { display:flex; flex-wrap:wrap; column-gap:16px; }
.invoice-request-note-field { flex:3 1 340px; min-width:0; }
.invoice-request-recipient { flex:1 1 160px; min-width:0; overflow-wrap:anywhere; }
.invoice-subject-hint { flex-basis: 100%; margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.invoice-request-note { white-space: pre-wrap; overflow-wrap: anywhere; }
.invoice-selection-settings{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0;font-size:12px}
.invoice-combined-actions{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:20px 0 8px;padding-top:14px;border-top:1px solid var(--el-border-color)}
.invoice-combined-actions h4{margin:0;font-size:14px}
.invoice-customer-group { margin-top: 16px; border: 1px solid var(--el-border-color-light); border-radius: 6px; padding: 12px; }
.invoice-customer-heading { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px 16px; margin-bottom: 8px; }
.invoice-customer-heading h3 { margin: 0; }
.el-descriptions + .el-descriptions { margin-top: 16px; }
:global(.invoice-workflow-dialog) { display:flex; flex-direction:column; max-height:90vh; overflow:hidden; }
:global(.invoice-workflow-dialog > .el-dialog__body) { flex:1; min-height:0; overflow:auto; }
:global(.invoice-workflow-dialog > .el-dialog__header),
:global(.invoice-workflow-dialog > .el-dialog__footer) { flex:none; }
</style>

<style scoped>
.invoice-statement-scroll{max-height:55vh;overflow-y:scroll;overflow-x:auto;overscroll-behavior:contain;scrollbar-gutter:stable}summary{cursor:pointer}
</style>
