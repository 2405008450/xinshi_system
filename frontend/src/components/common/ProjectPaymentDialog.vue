<template>
  <DraggableFormDialog :model-value="modelValue" class="project-payment-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="付款情况" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading">
      <AppForm ref="formRef" :model="form" label-position="top" :disabled="!canWrite||saving">
        <el-form-item v-if="!deferSave&&!lockProject" label="项目"><el-select v-model="selectedId" filterable remote :remote-method="searchProjects" :loading="searching" :disabled="loading" placeholder="搜索订单号、项目名称或客户" style="width:100%" @change="changeProject"><el-option v-for="project in options" :key="project.id" :value="project.id" :label="`${project.orderNo} · ${project.projectName||'-'}`" /></el-select></el-form-item>
        <el-form-item label="订单号"><ReadonlyField :model-value="orderNo||'保存项目后自动生成'" source="auto" /></el-form-item>
        <el-descriptions v-if="!isFull" :column="3" border class="payment-summary"><el-descriptions-item label="预定合计">{{total('planned_amount')}}</el-descriptions-item><el-descriptions-item label="实际付款合计">{{total('actual_amount')}}</el-descriptions-item><el-descriptions-item label="付款状态">{{paymentStatus}}</el-descriptions-item></el-descriptions>
        <PaymentConfirmationFields :model-value="form.confirmation" :project-id="selectedId" @update:model-value="updateConfirmation" />
        <p v-if="isFull" class="payment-help">已确认全款，无需填写分期明细；已有明细会保留。</p>
        <template v-if="!isFull">
        <div v-for="(item,index) in form.payments" :key="item.id||index" class="project-payment-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`付款明细 ${index+1}`">
          <div class="payment-row-heading"><strong>付款明细 {{index+1}}</strong><el-button link type="danger" @click="removePayment(index)">移除</el-button></div>
          <el-row :gutter="12"><el-col :xs="12" :md="6"><el-form-item label="阶段"><el-select v-model="item.stage_type" @change="syncFromDetails"><el-option label="定金" value="deposit" /><el-option label="中期款" value="mid" /><el-option label="尾款" value="final" /></el-select></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="期次"><el-input-number v-model="item.stage_no" :min="1" :max="999" :precision="0" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="预定金额"><el-input-number v-model="item.planned_amount" :min="0" :precision="2" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="实际金额"><el-input-number v-model="item.actual_amount" @change="syncFromDetails" :min="0" :precision="2" :controls="false" /></el-form-item></el-col></el-row>
          <el-row :gutter="12"><el-col :xs="24" :md="12"><el-form-item label="付款时间"><el-date-picker v-model="item.payment_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" clearable /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="付款方式"><PaymentAccountSelect v-model="item.payment_method" @update:model-value="syncFromDetails" /></el-form-item></el-col></el-row>
        </div>
        <el-button @click="addPayment">新增付款明细</el-button>
        </template>
      </AppForm>
      <p v-if="deferSave" class="payment-help">付款明细随项目一起保存。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="reloadPayment">重新加载付款情况</el-button></el-alert>
    </div>
    <template #footer><el-button :disabled="saving" @click="close(false)">取消</el-button><el-button v-if="canWrite" type="primary" :disabled="loading||(!deferSave&&!selectedId)" :loading="saving" @click="save">{{deferSave?'应用到项目':'保存付款情况'}}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import api from '@/api'
import {getCustomerFinancePage} from '@/api/translationCustomerFinance'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {businessDateTimeInputValue} from '@/utils/dateTime'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import ReadonlyField from './ReadonlyField.vue'
import PaymentConfirmationFields from './PaymentConfirmationFields.vue'
import PaymentAccountSelect from './PaymentAccountSelect.vue'
import {paymentConfirmationForm,paymentConfirmationPayload,paymentChangeEvent,notifyPaymentChanged} from '@/utils/paymentConfirmation'
const props=defineProps({modelValue:Boolean,projects:{type:Array,default:()=>[]},query:{type:Object,default:()=>({})},draftProject:{type:Object,default:null},draft:{type:Object,default:null},deferSave:Boolean,initialProjectId:{type:String,default:''},lockProject:Boolean,confirmationDraft:{type:Object,default:null}})
const emit=defineEmits(['update:modelValue','update:draft','saved'])
const canWrite=hasPermission('projects:write')||hasPermission('finance:write')
const body=ref(),formRef=ref(),options=ref([]),selectedId=ref(''),orderNo=ref(''),loading=ref(false),searching=ref(false),saving=ref(false),error=ref(''),form=reactive({payments:[],confirmation:paymentConfirmationForm()})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let version='',original='',loadedId='',sequence=0,searchSequence=0,controller,loadedPayments=[]
const paymentSource=`payment-dialog-${Math.random().toString(36).slice(2)}`
const isFull=computed(()=>form.confirmation.isPaid&&form.confirmation.paymentOption==='full')
const hasFinal=computed(()=>!isFull.value&&form.payments.some(item=>item.stage_type==='final'))
const cents=value=>BigInt(Number(value||0).toFixed(2).replace('.',''))
const totalCents=key=>form.payments.reduce((sum,item)=>sum+cents(item[key]),0n)
const money=value=>`${value/100n}.${String(value%100n).padStart(2,'0')}`
const total=key=>money(totalCents(key))
const paymentStatus=computed(()=>isFull.value?'已付全款':hasFinal.value?'尾款核对（累计实付）':totalCents('actual_amount')>0n?'已付定金／部分付款':form.confirmation.isPaid?'已确认定金（待补充明细）':form.payments.length?'未付款':'未登记')
const signature=()=>JSON.stringify([form.payments,form.confirmation])
function assign(data){form.confirmation=paymentConfirmationForm(data.confirmation);version=data.version||'';orderNo.value=data.order_no||props.draftProject?.orderNo||'';form.payments=(data.payments||[]).map(item=>({...JSON.parse(JSON.stringify(item)),planned_amount:item.planned_amount==null?undefined:Number(item.planned_amount),actual_amount:item.actual_amount==null?undefined:Number(item.actual_amount),payment_time:item.payment_time?businessDateTimeInputValue(item.payment_time):null}));loadedPayments=JSON.parse(JSON.stringify(form.payments));original=signature()}
function addPayment(){const stage=form.payments.length?'mid':'deposit';form.payments.push({stage_type:stage,stage_no:Math.max(0,...form.payments.filter(item=>item.stage_type===stage).map(item=>item.stage_no))+1,planned_amount:undefined,actual_amount:undefined,payment_time:null,payment_method:form.confirmation.paymentAccount||''})}
function updateConfirmation(value){
  const selectingDeposit=value.isPaid&&value.paymentOption==='deposit'&&(!form.confirmation.isPaid||form.confirmation.paymentOption!=='deposit')
  form.confirmation=paymentConfirmationForm(value)
  if(selectingDeposit&&form.payments.length&&form.payments[0].actual_amount==null&&form.payments[0].planned_amount==null){form.payments[0].stage_type='deposit';form.payments[0].stage_no=Math.max(0,...form.payments.slice(1).filter(item=>item.stage_type==='deposit').map(item=>item.stage_no))+1}
  if(form.confirmation.isPaid&&form.confirmation.paymentOption==='deposit'&&!form.payments.length)addPayment()
  if(hasFinal.value)syncFromDetails()
  for(const item of form.payments)if(!item.payment_method)item.payment_method=form.confirmation.paymentAccount||''
}
function syncFromDetails(){
  if(isFull.value)return
  const actual=form.payments.filter(item=>Number(item.actual_amount||0)>0)
  const methods=[...new Set(actual.map(item=>item.payment_method).filter(Boolean))]
  form.confirmation={...form.confirmation,isPaid:actual.length>0||hasFinal.value,paymentOption:actual.length||hasFinal.value?'deposit':form.confirmation.paymentOption,paymentAccount:methods.length===1?methods[0]:methods.length>1?'':form.confirmation.paymentAccount,fullPaymentSource:hasFinal.value?'details':null,fullPaymentAmount:hasFinal.value&&form.payments.every(item=>item.actual_amount!=null)?Number(total('actual_amount')):null,fullMatchStatus:'pending'}
}
function removePayment(index){form.payments.splice(index,1);syncFromDetails()}
async function reloadPayment(){if(await confirmClose())await load()}
function onExternalPayment(event){
  const detail=event.detail
  if(!props.modelValue||detail?.projectId!==selectedId.value||detail.source===paymentSource||saving.value)return
  if(signature()===original)void load()
  else error.value='其他窗口已更新该订单的付款情况，当前草稿已保留，请重新加载后核对'
}
window.addEventListener(paymentChangeEvent,onExternalPayment)
async function searchProjects(keyword=''){const seq=++searchSequence;controller?.abort();controller=new AbortController();searching.value=true;try{const data=await getCustomerFinancePage({...props.query,keyword:keyword.trim()||undefined,skip:0,limit:100},{signal:controller.signal});if(seq===searchSequence){const current=options.value.find(row=>row.id===selectedId.value);options.value=data.items||[];if(current&&!options.value.some(row=>row.id===current.id))options.value.unshift(current)}}catch(e){if(seq===searchSequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目搜索失败')}finally{if(seq===searchSequence)searching.value=false}}
async function load(applyDraft=false){const seq=++sequence;loading.value=true;error.value='';try{if(!selectedId.value){assign({payments:[]});return}const data=await api.get(`/translation-payments/${selectedId.value}`);if(seq===sequence){assign(data);loadedId=selectedId.value;if(!options.value.some(option=>option.id===selectedId.value))options.value.unshift({id:selectedId.value,orderNo:data.order_no,projectName:data.project_name||''});if(applyDraft&&props.confirmationDraft){const draft=paymentConfirmationForm(props.confirmationDraft);if(draft.revision===form.confirmation.revision)updateConfirmation(draft);else error.value='付款状态已在其他窗口更新，请重新加载并核对当前草稿'}}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'付款情况加载失败')}finally{if(seq===sequence)loading.value=false}}
async function changeProject(){if(signature()!==original){try{await ElMessageBox.confirm('是否放弃未保存的付款修改并切换项目？','切换项目',{type:'warning'})}catch{selectedId.value=loadedId;return}}await load()}
async function confirmClose(){if(saving.value)return false;if(signature()!==original){try{await ElMessageBox.confirm('付款情况尚未保存，是否放弃修改？','关闭付款情况',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return false}}return true}
async function close(value){if(value===false&&await confirmClose())emit('update:modelValue',false)}
async function beforeClose(done){if(await confirmClose())done()}
async function save(){
  if(hasFinal.value){syncFromDetails();if(form.payments.some(item=>item.actual_amount==null))return ElMessage.warning('登记尾款后，请填写每次付款的实际金额')}
  if(loading.value||saving.value||error.value||!await formRef.value?.validate().catch(()=>false))return
  const items=isFull.value?loadedPayments:form.payments
  const keys=items.map(item=>`${item.stage_type}:${item.stage_no}`)
  if(new Set(keys).size!==keys.length)return ElMessage.warning('同一付款阶段的期次不能重复')
  const data={version,confirmation:paymentConfirmationPayload(form.confirmation),payments:items.map(item=>({...item,planned_amount:item.planned_amount??null,actual_amount:item.actual_amount??null,payment_time:item.payment_time?item.payment_time.replace(' ','T')+'+08:00':null}))}
  if(props.deferSave){emit('update:draft',data);original=signature();emit('update:modelValue',false);return}
  saving.value=true
  try{const result=await api.put(`/translation-payments/${selectedId.value}`,data);assign(result);notifyPaymentChanged(selectedId.value,result.confirmation,paymentSource);emit('saved',result);ElMessage.success('付款情况已保存')}
  catch(e){error.value=getLocalizedErrorMessage(e,'付款情况保存失败')}
  finally{saving.value=false}
}
watch(()=>props.modelValue,visible=>{sequence++;searchSequence++;controller?.abort();clearFieldSearch();loading.value=false;error.value='';if(!visible)return;options.value=[...props.projects];selectedId.value=props.deferSave?props.draftProject?.id||'':props.initialProjectId||options.value[0]?.id||'';loadedId=selectedId.value;if(props.deferSave&&props.draft){assign(props.draft)}else{assign({payments:[]});void load(true)}if(!props.deferSave&&!props.lockProject)void searchProjects()})
onBeforeUnmount(()=>{window.removeEventListener(paymentChangeEvent,onExternalPayment);sequence++;searchSequence++;controller?.abort()})
</script>
<style scoped>
:global(.project-payment-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-payment-dialog>.el-dialog__header),:global(.project-payment-dialog>.el-dialog__footer){flex:none}:global(.project-payment-dialog>.el-dialog__body){flex:1;min-height:0;overflow:auto}.project-payment-row{padding:14px;border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.payment-row-heading{display:flex;justify-content:space-between;margin-bottom:10px}.project-payment-row .el-input-number{width:100%}.payment-summary{margin-bottom:14px}.payment-help{font-size:12px;color:var(--el-text-color-secondary)}
</style>
