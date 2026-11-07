<template>
  <DraggableFormDialog :model-value="modelValue" class="project-payment-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="付款与追账" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template v-if="showFilters" #actions><span class="payment-manager-label">客户经理：<el-button :title="managerLabel" @click="openManagerPicker">{{managerLabel}}</el-button></span></template></DialogFieldSearchHeader></template>
    <div ref="body" v-loading="loading">
      <el-tabs v-if="!deferSave" v-model="activeTab" @tab-change="onPaymentTabChanged"><el-tab-pane label="付款登记" name="register" /><el-tab-pane label="付款查看" name="overview" /><el-tab-pane label="追账" name="collection" /></el-tabs>
      <AppForm v-if="showFilters" :model="paymentFilters" inline class="payment-filter-bar" @submit.prevent="applyPaymentFilters">
        <el-form-item label="账单月份"><el-date-picker v-model="paymentFilters.month" type="month" value-format="YYYY-MM" placeholder="全部月份" clearable style="width:150px" @change="applyPaymentFilters" /></el-form-item>
        <el-form-item label="客户"><el-input v-model="paymentFilters.client" placeholder="客户全称或简称" clearable style="width:190px" @input="queueClientSearch" @keyup.enter="applyPaymentFilters" /></el-form-item>
        <el-form-item label="付款状态"><el-select v-model="paymentFilters.status" clearable placeholder="全部状态" style="width:155px" @change="applyPaymentFilters"><el-option label="未付款" value="unpaid" /><el-option label="已付定金" value="deposit" /><el-option label="已付进度款" value="mid" /><el-option v-if="activeTab!=='collection'" label="已付全款（含尾款）" value="full" /><el-option label="已付款（含部分）" value="paid" /></el-select></el-form-item>
        <el-form-item><el-button :loading="searching" @click="applyPaymentFilters">查询</el-button><el-button @click="resetPaymentFilters">重置</el-button></el-form-item>
      </AppForm>
      <p v-if="showFilters" class="payment-filter-summary">匹配 {{projectTotal}} 个项目<span v-if="projectTotal>100">，可输入订单号或项目名称继续搜索</span></p>
      <AppForm v-show="activeTab==='register'" ref="formRef" :model="form" label-position="top" :disabled="!canWrite||saving">
        <el-form-item v-if="!deferSave&&!lockProject" label="项目"><el-select v-model="selectedId" filterable remote :remote-method="queueProjectSearch" :loading="searching" :disabled="loading" placeholder="搜索订单号、项目名称或客户" style="width:100%" @change="changeProject"><el-option v-for="project in options" :key="project.id" :value="project.id" :label="`${project.orderNo} · ${project.projectName||'-'} · ${project.clientShortName||'-'}`" /></el-select></el-form-item>
        <el-form-item label="订单号"><ReadonlyField :model-value="orderNo||'保存项目后自动生成'" source="auto" /></el-form-item>
        <el-descriptions v-if="depositSelected" :column="3" border class="payment-summary"><el-descriptions-item label="预定合计">{{total('planned_amount')}}</el-descriptions-item><el-descriptions-item label="实际付款合计">{{total('actual_amount')}}</el-descriptions-item><el-descriptions-item label="付款状态">{{paymentStatus}}</el-descriptions-item></el-descriptions>
        <PaymentConfirmationFields :model-value="form.confirmation" :project-id="selectedId" :details-in-payments="depositSelected" @update:model-value="updateConfirmation" />
        <p v-if="isFull" class="payment-help">已确认全款，无需填写分期明细；已有明细会保留。</p>
        <template v-if="depositSelected">
        <div v-for="(item,index) in form.payments" :key="item.id||index" class="project-payment-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`付款明细 ${index+1}`">
          <div class="payment-row-heading"><strong>付款明细 {{index+1}}</strong><el-button link type="danger" @click="removePayment(index)">移除</el-button></div>
          <el-row :gutter="12"><el-col :xs="12" :md="6"><el-form-item label="阶段"><ReadonlyField v-if="index===0&&depositSelected" model-value="定金" source="auto" /><el-select v-else v-model="item.stage_type" @change="syncFromDetails"><el-option label="定金" value="deposit" /><el-option label="中期款" value="mid" /><el-option label="尾款" value="final" /></el-select></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="期次"><el-input-number v-model="item.stage_no" :min="1" :max="999" :precision="0" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="预定金额"><el-input-number v-model="item.planned_amount" :min="0" :precision="2" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="实际金额"><el-input-number v-model="item.actual_amount" @change="syncFromDetails" :min="0" :precision="2" :controls="false" /></el-form-item></el-col></el-row>
          <el-row :gutter="12"><el-col :xs="24" :md="12"><el-form-item label="付款时间"><el-date-picker v-model="item.payment_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" clearable /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="付款方式"><PaymentAccountSelect v-model="item.payment_method" @update:model-value="syncFromDetails" /></el-form-item></el-col></el-row>
          <template v-if="index===0&&depositSelected"><el-form-item label="支付截图及备注"><ScreenshotInput v-model="form.confirmation.proofs" type="textarea" :rows="2" :maxlength="20000" placeholder="可粘贴、拖入或上传定金支付截图，填写付款备注" /></el-form-item><p class="payment-help">支付截图长期保存，与编辑收费窗口同步；清除后可在付款修改记录中查看原凭证。</p></template>
        </div>
        <el-button @click="addPayment">新增付款明细</el-button>
        </template>
      </AppForm>
      <section v-if="activeTab!=='register'" class="payment-overview">
        <div class="payment-overview-search"><el-input v-model="projectKeyword" placeholder="搜索订单号、项目名称" clearable style="width:280px" @input="queueProjectSearch" @keyup.enter="searchProjects(projectKeyword)" /><span v-if="activeTab==='collection'" class="payment-help">仅列未付款、已付定金及已付进度款的项目；金额请结合项目总价核对。</span></div>
        <el-table v-loading="searching" :data="options" border row-key="id" max-height="460" empty-text="暂无匹配项目"><el-table-column prop="orderNo" label="订单号" min-width="160" /><el-table-column prop="projectName" label="项目名称" min-width="200" show-overflow-tooltip /><el-table-column prop="clientShortName" label="客户简称" min-width="140" /><el-table-column label="付款状态" width="110"><template #default="{row}">{{paymentStatusLabels[row.paymentStatus]||'未付款'}}</template></el-table-column><el-table-column label="已付金额" min-width="120"><template #default="{row}">{{row.paymentActualTotal==null?'未登记金额':`${row.paymentCurrency||'CNY'} ${row.paymentActualTotal}`}}</template></el-table-column><el-table-column label="不含税总价" min-width="130"><template #default="{row}">{{formatPaymentTotals(row.totalsExclTax)}}</template></el-table-column><el-table-column label="含税总价" min-width="130"><template #default="{row}">{{formatPaymentTotals(row.totalsInclTax)}}</template></el-table-column><el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" @click="openPaymentRow(row)">{{canWrite?'付款登记':'查看'}}</el-button></template></el-table-column></el-table>
        <el-pagination v-model:current-page="projectPage" :page-size="20" :total="projectTotal" layout="total,prev,pager,next" @current-change="searchProjects(projectKeyword)" />
      </section>
      <p v-if="deferSave" class="payment-help">付款明细随项目一起保存。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="reloadPayment">重新加载付款情况</el-button></el-alert>
    </div>
    <DraggableFormDialog v-model="managerPickerVisible" title="客户经理筛选" width="min(560px, calc(100vw - 32px))" top="10vh" append-to-body>
      <el-radio-group v-model="managerDraftScope" class="payment-manager-choices"><el-radio value="self">本人（{{selfName}}）</el-radio><el-radio value="all">不指定人（全部订单）</el-radio><el-radio value="name">指定客户经理</el-radio></el-radio-group>
      <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" v-model="managerDraftIds" @options="cacheManagers" />
      <template #footer><el-button @click="managerPickerVisible=false">取消</el-button><el-button type="primary" @click="applyManager">确定</el-button></template>
    </DraggableFormDialog>
    <template #footer><el-button :disabled="saving" @click="close(false)">取消</el-button><el-button v-if="canWrite&&activeTab==='register'" type="primary" :disabled="loading||(!deferSave&&!selectedId)" :loading="saving" @click="save">{{deferSave?'应用到项目':'保存付款情况'}}</el-button></template>
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
import ScreenshotInput from './ScreenshotInput.vue'
import CustomerDepartmentManagerSelect from './CustomerDepartmentManagerSelect.vue'
import {paymentConfirmationForm,paymentConfirmationPayload,paymentChangeEvent,notifyPaymentChanged,fixFirstDepositStage,clearPaymentSelection} from '@/utils/paymentConfirmation'
const props=defineProps({modelValue:Boolean,projects:{type:Array,default:()=>[]},query:{type:Object,default:()=>({})},draftProject:{type:Object,default:null},draft:{type:Object,default:null},deferSave:Boolean,initialProjectId:{type:String,default:''},lockProject:Boolean,confirmationDraft:{type:Object,default:null}})
const emit=defineEmits(['update:modelValue','update:draft','saved'])
const canWrite=hasPermission('projects:write')||hasPermission('finance:write')
const body=ref(),formRef=ref(),options=ref([]),selectedId=ref(''),orderNo=ref(''),loading=ref(false),searching=ref(false),saving=ref(false),error=ref(''),form=reactive({payments:[],confirmation:paymentConfirmationForm()})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let version='',original='',loadedId='',sequence=0,searchSequence=0,controller,loadedPayments=[]
const paymentSource=`payment-dialog-${Math.random().toString(36).slice(2)}`
const isFull=computed(()=>form.confirmation.isPaid&&form.confirmation.paymentOption==='full')
const depositSelected=computed(()=>form.confirmation.isPaid&&form.confirmation.paymentOption==='deposit')
function ensureFirstDeposit(){if(depositSelected.value&&!form.payments.length)addPayment();fixFirstDepositStage(form.confirmation,form.payments);if(depositSelected.value&&form.payments[0]&&!form.payments[0].payment_method)form.payments[0].payment_method=form.confirmation.paymentAccount||''}
const hasFinal=computed(()=>!isFull.value&&form.payments.some(item=>item.stage_type==='final'))
const cents=value=>BigInt(Number(value||0).toFixed(2).replace('.',''))
const totalCents=key=>form.payments.reduce((sum,item)=>sum+cents(item[key]),0n)
const money=value=>`${value/100n}.${String(value%100n).padStart(2,'0')}`
const total=key=>money(totalCents(key))
const paymentStatus=computed(()=>isFull.value?'已付全款':hasFinal.value?'尾款核对（累计实付）':totalCents('actual_amount')>0n?'已付定金／部分付款':form.confirmation.isPaid?'已确认定金（待补充明细）':form.payments.length?'未付款':'未登记')
const signature=()=>JSON.stringify([form.payments,form.confirmation])
function assign(data){form.confirmation=paymentConfirmationForm(data.confirmation);version=data.version||'';orderNo.value=data.order_no||props.draftProject?.orderNo||'';form.payments=(data.payments||[]).map(item=>({...JSON.parse(JSON.stringify(item)),planned_amount:item.planned_amount==null?undefined:Number(item.planned_amount),actual_amount:item.actual_amount==null?undefined:Number(item.actual_amount),payment_time:item.payment_time?businessDateTimeInputValue(item.payment_time):null}));loadedPayments=JSON.parse(JSON.stringify(form.payments));original=signature();if(!form.confirmation.isPaid){form.payments=[];if(loadedPayments.length)form.confirmation=clearPaymentSelection(form.confirmation)}else ensureFirstDeposit()}
function addPayment(){if(!depositSelected.value)return;const stage=form.payments.length?'mid':'deposit';form.payments.push({stage_type:stage,stage_no:Math.max(0,...form.payments.filter(item=>item.stage_type===stage).map(item=>item.stage_no))+1,planned_amount:undefined,actual_amount:undefined,payment_time:null,payment_method:form.confirmation.paymentAccount||''})}
function updateConfirmation(value){
  form.confirmation=paymentConfirmationForm(value)
  if(!form.confirmation.isPaid){form.payments=[];loadedPayments=[];form.confirmation=clearPaymentSelection(form.confirmation);return}
  ensureFirstDeposit()
  if(hasFinal.value)syncFromDetails()
  for(const item of form.payments)if(!item.payment_method)item.payment_method=form.confirmation.paymentAccount||''
}
function syncFromDetails(){
  if(isFull.value)return
  const actual=form.payments.filter(item=>Number(item.actual_amount||0)>0)
  const methods=[...new Set(actual.map(item=>item.payment_method).filter(Boolean))]
  form.confirmation={...form.confirmation,isPaid:depositSelected.value||actual.length>0||hasFinal.value,paymentOption:actual.length||hasFinal.value?'deposit':form.confirmation.paymentOption,paymentAccount:methods.length===1?methods[0]:methods.length>1?'':form.confirmation.paymentAccount,fullPaymentSource:hasFinal.value?'details':null,fullPaymentAmount:hasFinal.value&&form.payments.every(item=>item.actual_amount!=null)?Number(total('actual_amount')):null,fullMatchStatus:'pending'}
}
function removePayment(index){form.payments.splice(index,1);ensureFirstDeposit();syncFromDetails()}
async function reloadPayment(){if(await confirmClose())await load()}
function onExternalPayment(event){
  const detail=event.detail
  if(!props.modelValue||detail?.projectId!==selectedId.value||detail.source===paymentSource||saving.value)return
  if(signature()===original)void load()
  else error.value='其他窗口已更新该订单的付款情况，当前草稿已保留，请重新加载后核对'
}
window.addEventListener(paymentChangeEvent,onExternalPayment)
const activeTab=ref('register'),projectPage=ref(1)
const paymentStatusLabels={unpaid:'未付款',deposit:'已付定金',mid:'已付进度款',full:'已付全款'}
const formatPaymentTotals=value=>Object.entries(value||{}).map(([currency,amount])=>`${currency} ${amount}`).join('；')||'未填写'
async function onPaymentTabChanged(){projectPage.value=1;if(activeTab.value==='collection'&&paymentFilters.status==='full')paymentFilters.status='';await searchProjects(projectKeyword.value)}
async function openPaymentRow(row){if(!await confirmClose())return;selectedId.value=row.id;activeTab.value='register';await load()}
const showFilters=computed(()=>!props.deferSave&&!props.lockProject)
const paymentFilters=reactive({month:'',client:'',status:''}),projectKeyword=ref(''),projectTotal=ref(0)
const selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const managerScope=ref('self'),managerIds=ref([]),managerNames=ref({}),managerPickerVisible=ref(false),managerDraftScope=ref('self'),managerDraftIds=ref([])
const managerLabel=computed(()=>managerScope.value==='self'?`本人（${selfName}）`:managerScope.value==='name'?`指定（${managerIds.value.length}人）：${managerIds.value.map(id=>managerNames.value[id]||'已选人员').join('、')}`:'不指定人（全部订单）')
let filterTimer,projectTimer,lastFilters=''
const filterSignature=()=>JSON.stringify({filters:paymentFilters,scope:managerScope.value,ids:managerIds.value})
function cacheManagers(people){managerNames.value={...managerNames.value,...Object.fromEntries(people.map(person=>[person.id,person.name]))}}
function openManagerPicker(){managerDraftScope.value=managerScope.value;managerDraftIds.value=[...managerIds.value];managerPickerVisible.value=true}
async function applyManager(){managerScope.value=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value;managerIds.value=managerScope.value==='name'?[...managerDraftIds.value]:[];managerPickerVisible.value=false;await applyPaymentFilters()}
function initPaymentFilters(){Object.assign(paymentFilters,{month:props.query.billing_month||'',client:'',status:''});projectKeyword.value='';managerIds.value=[...(props.query.manager_ids||[])];managerScope.value=managerIds.value.length?'name':props.query.only_mine?'self':'all';lastFilters=filterSignature()}
function paymentQuery(keyword){return {keyword:keyword?.trim()||undefined,billing_month:paymentFilters.month||undefined,client:paymentFilters.client.trim()||undefined,payment_status:paymentFilters.status||undefined,manager_ids:managerScope.value==='name'?managerIds.value:undefined,only_mine:managerScope.value==='self',include_payment_status:true,exclude_full:activeTab.value==='collection',payment_project_id:props.lockProject?selectedId.value||props.initialProjectId||undefined:undefined,skip:activeTab.value==='register'?0:(projectPage.value-1)*20,limit:activeTab.value==='register'?100:20}}
function queueClientSearch(value){clearTimeout(filterTimer);controller?.abort();searchSequence++;if(!value.trim())void applyPaymentFilters();else filterTimer=setTimeout(applyPaymentFilters,400)}
function queueProjectSearch(keyword=''){projectPage.value=1;projectKeyword.value=keyword;clearTimeout(projectTimer);controller?.abort();searchSequence++;if(!keyword.trim())void searchProjects('');else projectTimer=setTimeout(()=>searchProjects(keyword),400)}
async function applyPaymentFilters(){clearTimeout(filterTimer);clearTimeout(projectTimer);if(saving.value)return;if(!await confirmClose()){const previous=JSON.parse(lastFilters);Object.assign(paymentFilters,previous.filters);managerScope.value=previous.scope;managerIds.value=previous.ids;return}lastFilters=filterSignature();projectPage.value=1;projectKeyword.value='';await searchProjects('',true)}
async function resetPaymentFilters(){Object.assign(paymentFilters,{month:'',client:'',status:''});managerIds.value=[];managerScope.value=props.query.only_mine?'self':'all';await applyPaymentFilters()}
async function searchProjects(keyword='',selectFirst=false){clearTimeout(projectTimer);const seq=++searchSequence;controller?.abort();controller=new AbortController();searching.value=true;try{const data=await getCustomerFinancePage(paymentQuery(keyword),{signal:controller.signal});if(seq===searchSequence){options.value=data.items||[];projectTotal.value=data.total||0;if(selectFirst){selectedId.value=options.value[0]?.id||'';await load()}}}catch(e){if(seq===searchSequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目搜索失败')}finally{if(seq===searchSequence)searching.value=false}}

async function load(applyDraft=false){const seq=++sequence;loading.value=true;error.value='';try{if(!selectedId.value){assign({payments:[]});loadedId='';return}const data=await api.get(`/translation-payments/${selectedId.value}`);if(seq===sequence){assign(data);loadedId=selectedId.value;if(!options.value.some(option=>option.id===selectedId.value))options.value.unshift({id:selectedId.value,orderNo:data.order_no,projectName:data.project_name||''});if(applyDraft&&props.confirmationDraft){const draft=paymentConfirmationForm(props.confirmationDraft);if(draft.revision===form.confirmation.revision)updateConfirmation(draft);else error.value='付款状态已在其他窗口更新，请重新加载并核对当前草稿'}}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'付款情况加载失败')}finally{if(seq===sequence)loading.value=false}}
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
  try{const result=await api.put(`/translation-payments/${selectedId.value}`,data);assign(result);notifyPaymentChanged(selectedId.value,result.confirmation,paymentSource);emit('saved',result);void searchProjects(projectKeyword.value);ElMessage.success('付款情况已保存')}
  catch(e){error.value=getLocalizedErrorMessage(e,'付款情况保存失败')}
  finally{saving.value=false}
}
watch(()=>props.modelValue,visible=>{sequence++;searchSequence++;controller?.abort();clearFieldSearch();loading.value=false;error.value='';if(!visible){managerPickerVisible.value=false;clearTimeout(filterTimer);clearTimeout(projectTimer);return}activeTab.value='register';projectPage.value=1;initPaymentFilters();options.value=[...props.projects];selectedId.value=props.deferSave?props.draftProject?.id||'':props.initialProjectId||options.value[0]?.id||'';loadedId=selectedId.value;if(props.deferSave&&props.draft){assign(props.draft)}else{assign({payments:[]});void load(true)}if(!props.deferSave&&!props.lockProject)void searchProjects()})
onBeforeUnmount(()=>{clearTimeout(filterTimer);clearTimeout(projectTimer);window.removeEventListener(paymentChangeEvent,onExternalPayment);sequence++;searchSequence++;controller?.abort()})
</script>
<style scoped>
:global(.project-payment-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-payment-dialog>.el-dialog__header),:global(.project-payment-dialog>.el-dialog__footer){flex:none}:global(.project-payment-dialog>.el-dialog__body){flex:1;min-height:0;overflow:auto}.project-payment-row{padding:14px;border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.payment-row-heading{display:flex;justify-content:space-between;margin-bottom:10px}.project-payment-row .el-input-number{width:100%}.payment-summary{margin-bottom:14px}.payment-help{font-size:12px;color:var(--el-text-color-secondary)}
.payment-overview-search{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}.payment-overview .el-pagination{margin-top:10px}.payment-filter-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.payment-filter-bar :deep(.el-form-item){margin-right:0;margin-bottom:8px}.payment-filter-summary{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 8px}.payment-manager-label{font-size:14px;font-weight:400;color:var(--el-text-color-secondary)}.payment-manager-label .el-button{max-width:300px;white-space:normal;height:auto;min-height:30px}.payment-manager-choices{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
</style>
