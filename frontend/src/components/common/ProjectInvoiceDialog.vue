<template>
  <component :is="inline ? InlineInvoice : DraggableFormDialog" :model-value="modelValue" class="project-invoice-dialog" width="min(800px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="$emit('update:modelValue',$event)">
    <template v-if="!compactOrder" #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword"
        :title="mergedInvoice || context.merged ? `发票 · ${mergedSettlementLabel}` : `发票 · ${display.orderNo||''}${context.level ? `（${context.level}）` : ''}`" copyable-title
        :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch">
        <template v-if="!mergedInvoice && !context.merged && display.clientName && display.clientName!=='-'" #actions>
          <span class="invoice-header-client">客户 {{ display.clientName }}</span>
        </template>
      </DialogFieldSearchHeader>
    </template>
    <div ref="body" v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <CustomerInvoiceProfile v-if="info.clientId && !requestId && !compactOrder"
        :client-id="info.clientId" :sub-client-id="info.subClientId" :can-write="canWriteClient" collapsible default-collapsed />
      <section v-if="mergedInvoice && modelValue" :key="context.projectId" class="invoice-merged-summary">
        <h4>合并开票金额 <strong>{{ formatTotals(mergedScope.invoiceTotals) }}</strong></h4>
        <el-alert v-if="mergedScope.items.some(row=>row.invoiceRequired && !row.hasInvoiceAmount)"
          type="warning" :closable="false" title="部分需开票订单缺少含税金额，合计仅包含已填写的金额。" />
        <details v-for="row in mergedScope.items" :key="row.id" class="invoice-merged-order"
          @toggle="openMergedOrder(row.id, $event.currentTarget.open)">
          <summary>
            <strong>{{row.orderNo}}</strong>
            <span>{{row.projectName}}</span>
            <span>{{row.invoiceRequired===false?'无需开票':row.invoiceRequired==null?'开票待确认':invoiceStatusLabels[row.invoiceStatus]||'未开票'}}</span>
            <span>{{formatTotals(row.invoiceTotals)}}</span>
          </summary>
          <OrderPriceDetails :order="row.priceDetails" />
          <template v-if="openedMergedOrders.has(row.id)">
            <InvoiceChildOrderSummary v-if="row.hasChildren" :order="row" expanded />
            <ProjectInvoiceDialog :ref="instance=>setMergedEditor(row.id,instance)" inline compact-order persistent-inline
              :model-value="true" :readonly="readonly" :context="{projectId:row.id,orderId:row.id}" @saved="onMergedOrderSaved" />
          </template>
        </details>
      </section>
      <AppForm v-else-if="invoiceScopeAvailable" ref="formRef" class="invoice-form" :model="form" label-position="top" :disabled="loading||saving||!canWrite">
        <div class="invoice-form-row invoice-form-status">
          <el-form-item label="是否需发票"><ReadonlyField :model-value="display.required==null?'待判断':display.required?'需':'无需'" source="auto" /><small>{{special?'在特殊结算中设置。':'在价格与付款中设置。'}}</small></el-form-item>
          <el-form-item :label="context.merged?'合并开票金额':'项目计费金额'"><ReadonlyField :model-value="formatTotals(display.totals)" source="auto" /><OrderPriceDetails :order="display.priceDetails" /></el-form-item>
          <el-form-item label="发票状态" prop="invoiceStatus" :rules="[{required:true,message:'请选择发票状态',trigger:'change'}]"><el-select v-model="form.invoiceStatus" style="width:100%"><el-option v-for="option in invoiceStatusOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <div class="invoice-form-row invoice-form-attachments">
          <el-form-item label="发票说明"><ReadonlyField :model-value="display.note||'-'" source="auto" /><small>说明在价格与付款中填写。</small></el-form-item>
          <el-form-item label="发票截图及备注">
            <ScreenshotInput v-model="form.proofs" type="textarea" allow-invoice-files :invoice-request-id="requestId" :invoice-order-no="display.orderNo" :rows="3" :maxlength="20000"
              :disabled="loading || saving || !canWrite || !context.projectId" placeholder="拖入 PDF、OFD 发票或截图，也可填写开票备注"
              @uploading-change="onUploadingChange" @attachment-added="attachmentAdded = true" />
            <el-button v-if="canWrite && screenshotIds(form.proofs).length" link type="danger"
              :disabled="loading || saving || uploading" @click="removeInvoices">删除发票</el-button>
          </el-form-item>
        </div>
        <p v-if="!context.projectId">保存项目后可保存发票信息。</p>
        <p v-if="!compactOrder">{{context.merged?'发票状态和附件会同步保存到本次合并开票的各订单。':special?'发票状态和附件按特殊结算订单保存。':'发票状态和附件按母订单保存，三个入口共用同一份记录。'}}</p>
      </AppForm>
      <details v-if="info.history?.length && !mergedInvoice" class="invoice-records-disclosure">
        <summary>发票修改记录（{{info.history.length}}）</summary>
        <el-collapse>
          <el-collapse-item v-for="event in [...info.history].reverse()" :key="event.id" :name="event.id"
            :title="`${event.actor_name} · ${formatBusinessDateTime(event.at)}`">
            <div v-for="(value, label) in {'修改前':event.before,'修改后':event.after}" :key="label">
              <strong>{{label}} · {{invoiceStatusLabels[value.invoice_status]||'未开票'}}</strong>
              <ScreenshotText :text="value.proofs||''" />
            </div>
          </el-collapse-item>
        </el-collapse>
      </details>
      <el-alert v-if="scopeError" :title="scopeError" type="warning" :closable="false">
        <el-button link type="primary" @click="scopeRefresh++">重新加载结算范围</el-button>
      </el-alert>
      <el-skeleton v-else-if="!invoiceScopeAvailable" :rows="2" animated />
      <details v-if="mergedScope?.merged && !mergedInvoice" :key="context.projectId" class="invoice-records-disclosure">
        <summary>多单合并结款（发票） · {{ mergedScope.items.length }} 个项目</summary>
        <el-table :data="mergedScope.items" row-key="id" border max-height="320">
          <el-table-column prop="orderNo" label="订单号" min-width="145" />
          <el-table-column prop="projectName" label="项目名称" min-width="150" show-overflow-tooltip />
          <el-table-column label="计费金额" min-width="120">
            <template #default="{row}">{{ formatTotals(row.billingTotals) }}</template>
          </el-table-column>
          <el-table-column label="发票状态" min-width="100">
            <template #default="{row}">{{ row.invoiceRequired===false ? '无需' : row.invoiceRequired==null ? '待判断' : invoiceStatusLabels[row.invoiceStatus] || '未开票' }}</template>
          </el-table-column>
        </el-table>
      </details>
      <InvoiceChildOrderSummary v-if="modelValue && context.order && !requestId && !mergedInvoice && !compactOrder && invoiceScopeAvailable" :key="context.order.id" :order="context.order" :special="special" />
      <details v-if="info.clientId && !requestId && !compactOrder" :key="context.orderId" class="invoice-records-disclosure">
        <summary>客户项目开票记录</summary>
        <CustomerInvoiceRecords :client-id="info.clientId" :sub-client-id="info.subClientId" :settlement-scope="special?'special':'standard'" :allow-open="false" hide-heading />
      </details>
    </div>
    <template #footer>
      <el-button v-if="!persistentInline" :disabled="saving || uploading" @click="close">{{inline?'收起':'关闭'}}</el-button>
      <el-button v-if="canWrite && !mergedInvoice && invoiceScopeAvailable" :type="canNotify ? 'default' : 'primary'" :loading="saving" :disabled="loading || uploading || !version || !context.projectId" @click="save()">保存发票</el-button>
      <el-button v-if="canNotify && canWrite && !mergedInvoice && invoiceScopeAvailable" type="primary" :loading="saving" :disabled="loading || uploading || !version || !screenshotIds(form.proofs).length || form.invoiceStatus !== 'issued'" @click="save(true)">通知开票完成</el-button>
    </template>
  </component>
</template>
<script setup>
import {computed,defineComponent,h,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import api from '@/api'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {invoiceStatusOptions,invoiceStatusLabels} from '@/utils/documentRequirements'
import {getProjectInvoiceScope} from '@/api/translationCustomerFinance'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import ReadonlyField from './ReadonlyField.vue'
import ScreenshotInput from './ScreenshotInput.vue'
import ScreenshotText from './ScreenshotText.vue'
import {formatBusinessDateTime} from '@/utils/dateTime'
import CustomerInvoiceProfile from './CustomerInvoiceProfile.vue'
import CustomerInvoiceRecords from './CustomerInvoiceRecords.vue'
import InvoiceChildOrderSummary from './InvoiceChildOrderSummary.vue'
import {connectInvoiceParties, invoicePartiesEvent, notifyInvoiceParties} from '@/api/invoiceParties'
import {screenshotIds,screenshotText} from '@/utils/screenshotReferences'
import {translationSettlementModeLabels} from '@/utils/settlementModes'
const props=defineProps({modelValue:Boolean,context:{type:Object,default:()=>({})},requestId:String,canDeliver:Boolean,readonly:Boolean,inline:Boolean,persistentInline:Boolean,compactOrder:Boolean,special:Boolean})
const emit=defineEmits(['update:modelValue','saved','invoice-scope-loaded'])
const InlineInvoice=defineComponent({
  inheritAttrs:false,
  setup(_, {slots}){
    return ()=>h('section',{class:'project-invoice-inline', 'aria-label':'发票详情'},[
      slots.header?h('header',slots.header()):null,
      slots.default?.(),
      h('footer',slots.footer?.()),
    ])
  },
})
const canWrite=computed(()=>!props.readonly&&(props.requestId ? props.canDeliver : hasPermission('projects:write')||hasPermission('finance:write')))
const invoiceUrl=computed(()=>props.requestId
  ? `/invoice-workflow/requests/${props.requestId}/projects/${props.context.projectId}/invoice`
  : `/translation-customer-finance/project/${props.context.projectId}/invoice`)
const workflowParams=computed(()=>({combined:props.requestId&&props.context.merged||undefined,
  special:props.special&&!props.requestId||undefined}))
const invoiceParams=computed(()=>({order_id:props.context.orderId||undefined,...workflowParams.value}))
const canWriteClient=computed(()=>!props.readonly&&hasPermission('clients:write'))
const body=ref(),formRef=ref(),loading=ref(false),saving=ref(false),error=ref(''),info=ref({}),form=reactive({invoiceStatus:'unissued',proofs:''})
const uploading = ref(false)
const attachmentAdded = ref(false)
const canNotify = computed(() => Boolean(props.requestId ? props.canDeliver : info.value.canNotifyRequester))
async function onUploadingChange(value) {
  uploading.value = value
  if (value || !attachmentAdded.value || !props.modelValue) return
  attachmentAdded.value = false
  form.invoiceStatus = 'issued'
  await save(false,true)
}
async function removeInvoices() {
  try {
    await ElMessageBox.confirm('删除当前发票附件并将状态改为未开票？修改前后的内容将保留在发票修改记录中。', '删除发票', {
      confirmButtonText:'确认删除',cancelButtonText:'取消',type:'warning',
    })
  } catch { return }
  form.proofs=screenshotText(form.proofs)
  form.invoiceStatus='unissued'
  await save(false,true)
}
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const camel=data=>Object.fromEntries(Object.entries(data).map(([key,value])=>[key.replace(/_([a-z])/g,(_,letter)=>letter.toUpperCase()),value]))
const financePreview=ref(null)
const display=computed(()=>({...info.value,...props.context.preview,...financePreview.value}))
const mergedScope=ref(null),scopeError=ref(''),scopeRefresh=ref(0)
const mergedSettlementLabel=computed(()=>translationSettlementModeLabels[mergedScope.value?.settlementMode || props.context.order?.paymentMethod]||translationSettlementModeLabels.monthly)
const mergedInvoice=computed(()=>props.inline&&!props.compactOrder&&!!mergedScope.value?.merged)
const invoiceScopeAvailable=computed(()=>props.special||!props.inline||!props.persistentInline||props.compactOrder||!props.context.projectId||mergedScope.value!==null)
const openedMergedOrders=reactive(new Set()),mergedEditors=new Map()
function openMergedOrder(id,open){if(open)openedMergedOrders.add(id)}
function setMergedEditor(id,instance){if(instance)mergedEditors.set(id,instance);else mergedEditors.delete(id)}
function onMergedOrderSaved(result){emit('saved',result);scopeRefresh.value++}
watch(()=>[props.modelValue,props.context.projectId,props.requestId,scopeRefresh.value],async ([visible,projectId,requestId],previous,onCleanup)=>{
  if(projectId!==previous?.[1]||!visible){mergedScope.value=null;openedMergedOrders.clear()}
  scopeError.value=''
  if(!visible||!projectId||requestId||props.compactOrder||props.special)return
  const request=new AbortController()
  onCleanup(()=>request.abort())
  try{
    const scope=await getProjectInvoiceScope(projectId,{signal:request.signal})
    if(!request.signal.aborted){
      mergedScope.value=scope
      emit('invoice-scope-loaded',scope,projectId)
    }
  }catch(error){
    if(!request.signal.aborted)scopeError.value=getLocalizedErrorMessage(error,'合并结款项目加载失败')
  }
},{immediate:true})
const formatTotals=totals=>Object.entries(totals||{}).map(([currency,amount])=>`${currency} ${Number(amount).toFixed(2)}`).join('；')||'-'
let original='',version='',sequence=0,controller
const signature=()=>JSON.stringify(form)
async function load(){const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';version='';clearFieldSearch();Object.assign(form,{invoiceStatus:'unissued',proofs:''});info.value={};try{if(!props.context.projectId)return;const data=camel(await api.get(invoiceUrl.value,{params:invoiceParams.value,signal:controller.signal}));if(current!==sequence)return;info.value=data;version=data.version;Object.assign(form,{invoiceStatus:data.invoiceStatus,proofs:data.proofs||''})}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'发票信息加载失败')}finally{if(current===sequence){original=signature();loading.value=false}}}
async function save(deliver = false, keepOpen = false) {
  if (!canWrite.value || loading.value || saving.value || uploading.value || !version) return
  if (!await formRef.value?.validate().catch(()=>false) || saving.value || uploading.value) return
  saving.value = true
  error.value = ''
  let savedProjectId
  try {
    const projectId = props.context.projectId
    const data = camel(await api.put(invoiceUrl.value, {
      version, invoice_status:form.invoiceStatus, proofs:form.proofs,
    }, {params:invoiceParams.value}))
    version = data.version
    info.value = {...info.value, ...data}
    original = signature()
    savedProjectId = projectId
    if (deliver) {
      const notifyUrl = props.requestId
        ? `/invoice-workflow/requests/${props.requestId}/projects/${projectId}/deliver`
        : `/invoice-workflow/projects/${props.special?props.context.orderId||projectId:projectId}/notify-issued`
      await api.post(notifyUrl, {version}, {params:workflowParams.value})
    }
    emit('saved', data)
    ElMessage.success(deliver ? '开票完成通知已发送' : '发票信息已保存')
    if(props.persistentInline)await load()
    else if(!keepOpen)emit('update:modelValue', false)
  } catch (e) {
    error.value = getLocalizedErrorMessage(e, deliver ? '发票发送失败' : '发票保存失败')
  } finally {
    if (savedProjectId) {
      notifyInvoiceParties({kind:'records', clientId:String(info.value.clientId || ''), projectId:savedProjectId,requestId:props.requestId})
      if(props.special)notifyInvoiceParties({kind:'special-settlement', projectId:savedProjectId})
      window.dispatchEvent(new CustomEvent('translation-invoice-changed', {detail:{projectId:savedProjectId}}))
    }
    saving.value = false
  }
}
async function confirmClose(){
  if(saving.value||uploading.value)return false
  if(mergedInvoice.value){
    for(const editor of mergedEditors.values())if(!await editor.confirmClose())return false
  }else if(!loading.value&&signature()!==original){
    try{await ElMessageBox.confirm('发票信息有未保存修改，是否放弃？','关闭发票',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return false}
  }
  return true
}
async function beforeClose(done){if(await confirmClose())done()}
defineExpose({beforeClose,confirmClose})
function close(){void beforeClose(()=>emit('update:modelValue',false))}
watch(()=>[props.modelValue,props.context.projectId,props.context.orderId],()=>{
  financePreview.value=null
  if(props.modelValue)void load()
  else{sequence++;controller?.abort()}
},{immediate:true})
function refreshFinancePreview(event){
  const item=event.detail?.financeItem
  if(!props.modelValue || props.requestId || !item || item.id!==props.context.projectId)return
  if(props.special){
    const url=invoiceUrl.value, params=invoiceParams.value
    void api.get(url,{params}).then(response=>{
      if(props.modelValue&&invoiceUrl.value===url&&invoiceParams.value.order_id===params.order_id){
        const {required,totals,priceDetails}=camel(response)
        financePreview.value={required,totals,priceDetails}
      }
    }).catch(()=>{})
    return
  }
  if(mergedScope.value?.merged)scopeRefresh.value++
  const orderId=props.context.orderId||item.id
  const findOrder=order=>order.id===orderId?order:(order.children||[]).map(findOrder).find(Boolean)
  const order=findOrder(item)
  if(order)financePreview.value={required:order.invoiceRequired,totals:order.billingTotals,priceDetails:order}
}
window.addEventListener('translation-statements-changed',refreshFinancePreview)
let settingsRequest
async function refreshSubClientSettings(event){
  if(!props.modelValue || props.requestId || !props.context.projectId || event.detail?.kind!=='sub-client-finance')return
  if(String(event.detail.clientId)!==String(info.value.clientId))return
  settingsRequest?.abort()
  const request=new AbortController()
  settingsRequest=request
  const url=invoiceUrl.value, params=invoiceParams.value
  try{
    const data=camel(await api.get(url,{params,signal:request.signal}))
    if(request.signal.aborted || !props.modelValue || url!==invoiceUrl.value || params.order_id!==invoiceParams.value.order_id)return
    const {clientName,subClientId,required,totals,priceDetails}=data
    info.value={...info.value,clientName,subClientId}
    financePreview.value={required,totals,priceDetails}
    scopeRefresh.value++
  }catch(cause){
    if(!request.signal.aborted)error.value=getLocalizedErrorMessage(cause,'发票的子客户设置刷新失败')
  }
}
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,refreshSubClientSettings)
onBeforeUnmount(()=>{
  window.removeEventListener('translation-statements-changed',refreshFinancePreview)
  window.removeEventListener(invoicePartiesEvent,refreshSubClientSettings)
  settingsRequest?.abort()
  sequence++
  controller?.abort()
})
</script>
<style scoped>
:global(.project-invoice-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-invoice-dialog>.el-dialog__header),:global(.project-invoice-dialog>.el-dialog__footer){flex:none}:global(.project-invoice-dialog>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}
.invoice-form{container-type:inline-size;container-name:invoice-form}
.invoice-form-row{display:grid;grid-template-columns:minmax(0,1fr);column-gap:16px}
.invoice-form small{width:100%;color:var(--el-text-color-secondary)}
.invoice-header-client{display:inline-block;max-width:min(18ch,28vw);overflow-wrap:anywhere;user-select:text}
.project-invoice-inline{min-width:0;margin-top:12px;padding:16px;border:1px solid var(--el-border-color-light);border-radius:8px}
:global(.project-invoice-inline>header){margin-bottom:12px}
:global(.project-invoice-inline>footer){display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
:global(.project-invoice-inline>footer .el-button){margin-left:0}
.invoice-records-disclosure>summary{cursor:pointer;padding:6px 0;font-weight:600}
.invoice-merged-summary{margin:16px 0}
.invoice-merged-summary h4{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 12px}
.invoice-merged-order{border-bottom:1px solid var(--el-border-color-light);padding:10px 0}
.invoice-merged-order>summary{cursor:pointer;line-height:1.5;overflow-wrap:anywhere}
.invoice-merged-order>summary span{margin-inline-start:12px}
.invoice-merged-order[open]>summary{margin-bottom:8px}
@container invoice-form (min-width:500px){
  .invoice-form-status{grid-template-columns:repeat(3,minmax(0,1fr))}
  .invoice-form-attachments{grid-template-columns:minmax(0,1fr) minmax(0,1.5fr)}
}
</style>
