<template>
  <span>
    <el-button :disabled="!targetId&&!deferSave" :link="scope==='project'&&!deferSave" type="primary" @click="open">{{scope==='client'?'口译参考价及调整记录':'价格与收费'}}</el-button>
    <DraggableFormDialog v-model="visible" append-to-body class="interpretation-finance-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" :before-close="close" :close-on-click-modal="false">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="scope==='client'?'客户口译参考价':`价格与收费${context.order_no?' · '+context.order_no:''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body" v-loading="loading||saving">
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <CustomerFinanceModuleTabs v-model="financeModule" module="interpretation" :enabled="scope==='project'" :client-id="context.client_id"><template #interpretation>
        <AppForm v-if="draft&&!loading" ref="form" :model="draft" label-position="top" :disabled="saving||!canWrite||!context.ready">
          <template v-if="scope==='project'"><el-form-item label="订单号"><ReadonlyField :model-value="context.order_no" source="auto" /></el-form-item><el-form-item label="项目名称"><ReadonlyField :model-value="context.project_name||'-'" source="auto" /></el-form-item><el-form-item label="客户简称"><ClientManagementLink :value="context.client_short_name" :row="context" /></el-form-item><el-form-item label="项目状态"><ReadonlyField :model-value="getProjectStatusLabel('interpretation',context.project_status)" source="auto" /></el-form-item><el-form-item label="客户参考价"><el-button :disabled="!context.reference_rates?.length" @click="adopt">采用匹配方向的客户参考价</el-button></el-form-item><el-form-item v-if="canWriteClients&&context.client_id&&context.library_revision!=null" label="同步客户参考价"><el-button @click="save(true)">保存并同步单价至客户信息…</el-button></el-form-item></template>
          <InterpretationFinanceFields v-model="draft" :directions="activeDirections" :reference-only="scope==='client'" />
          <template v-if="scope==='project'">
            <el-form-item label="客户说明"><el-input v-model="draft.settlement.customer_explanation" type="textarea" :rows="2" maxlength="5000" /></el-form-item>
            <el-form-item label="账单月份"><el-date-picker v-model="draft.settlement.billing_month" type="month" value-format="YYYY-MM" placeholder="默认按订单日期" /></el-form-item>
            <el-form-item label="计费税口径"><el-select v-model="draft.settlement.tax_basis" style="width:200px"><el-option label="不含税" value="excl_tax" /><el-option label="含税" value="incl_tax" /><el-option label="税口径未确认" value="legacy" /></el-select></el-form-item>
            <el-form-item label="当前计费合计"><ReadonlyField type="textarea" autosize :model-value="formatFinanceAmounts(interpretationFinanceTotals(draft))" source="auto" /></el-form-item>
            <el-form-item label="付款方式"><el-radio-group v-model="draft.settlement.payment_method"><el-radio value="individual">单项付款</el-radio><el-radio value="statement">对账单汇总付款</el-radio><el-radio value="monthly">月度汇总付款</el-radio></el-radio-group></el-form-item>
            <el-form-item label="收款状态"><el-select v-model="draft.settlement.payment_status" style="width:200px"><el-option label="未登记" value="unrecorded" /><el-option label="已收定金" value="deposit" /><el-option label="已收部分款" value="partial" /><el-option label="已收全款" value="full" /></el-select></el-form-item>
            <section v-for="(receipt,index) in draft.settlement.payments" :key="index" class="finance-receipt"
              data-dialog-field-search-group :data-dialog-field-search-group-title="'收款明细 '+(index+1)">
              <el-form-item label="实收金额" :prop="'settlement.payments.'+index+'.amount'" :rules="[{required:true,message:'请填写实收金额'}]"><el-input-number v-model="receipt.amount" :min="0" :precision="2" :controls="false" /></el-form-item>
              <el-form-item label="实收货币"><el-select v-model="receipt.currency" filterable allow-create><el-option v-for="code in interpretationCurrencies" :key="code" :value="code" /></el-select></el-form-item>
              <el-form-item label="收款日期"><el-date-picker v-model="receipt.received_on" type="date" value-format="YYYY-MM-DD" /></el-form-item>
              <el-form-item label="收款备注"><el-input v-model="receipt.note" maxlength="2000" /></el-form-item>
              <el-button link type="danger" @click="draft.settlement.payments.splice(index,1)">移除收款明细</el-button>
            </section>
            <el-button :disabled="draft.settlement.payments.length>=100" @click="draft.settlement.payments.push({currency:'CNY',received_on:null,note:''})">新增收款明细</el-button>
            <el-form-item label="付款说明"><el-input v-model="draft.settlement.payment_note" type="textarea" :rows="2" maxlength="5000" /></el-form-item>
            <el-form-item label="单据需求"><el-checkbox v-model="draft.settlement.quotation_required">需报价单</el-checkbox><el-checkbox v-model="draft.settlement.invoice_required">需发票</el-checkbox></el-form-item>
            <el-form-item label="单据">
              <el-button @click="quotationVisible=true">报价单</el-button>
              <el-button :disabled="!targetId" @click="statementVisible=true">已保存项目对账单</el-button>
            </el-form-item>
            <p v-if="deferSave">收费和报价单随项目保存，对账单使用已保存的收费。</p>
          </template>
        </AppForm>
        <p v-if="scope==='project'">对应税口径未填写的项目不参与该口径合计；未填写不代表零税率。</p>
        <el-descriptions v-if="scope==='project'&&targetId&&context.revision>0&&!loading" title="已保存的金额" :column="2" border><el-descriptions-item label="不含税总价">{{formatFinanceAmounts(context.totals_excl_tax)}}</el-descriptions-item><el-descriptions-item label="含税总价">{{formatFinanceAmounts(context.totals_incl_tax)}}</el-descriptions-item><el-descriptions-item label="原总价（税口径未确认）"><span class="finance-text">{{formatFinanceAmounts(context.totals)}}</span></el-descriptions-item><el-descriptions-item label="原调整总价（税口径未确认）"><span class="finance-text">{{formatFinanceAmounts(context.adjusted_totals)}}</span></el-descriptions-item></el-descriptions>
        <template v-if="scope==='client' && visible">
          <p v-if="signature()!==original" class="finance-text">请先保存或放弃当前修改，再引入项目单价。</p>
          <CustomerRateDifferences module="interpretation" :client-id="targetId" :revision="context.revision||0" :disabled="saving || signature()!==original" @saved="open" />
        </template>
        <template v-if="targetId"><h4>调整记录（{{historyTotal}}）</h4><el-collapse><el-collapse-item v-for="item in history" :key="item.id" :title="`第${item.revision}次 · ${item.actor_name} · ${formatTime(item.created_at)}`"><el-descriptions :column="1" border><el-descriptions-item label="调整前"><span class="finance-text">{{financeSummary(item.before)}}</span></el-descriptions-item><el-descriptions-item label="调整后"><span class="finance-text">{{financeSummary(item.after)}}</span></el-descriptions-item></el-descriptions></el-collapse-item></el-collapse>
        <el-pagination v-model:current-page="historyPage" :total="historyTotal" :page-size="10" layout="total, prev, pager, next" @current-change="loadHistory" /></template>
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button v-if="canWrite&&(scope==='client'||financeModule==='interpretation')" type="primary" :disabled="loading||!context.ready" :loading="saving" @click="save()">{{deferSave?'应用到项目':'保存'}}</el-button></template>
    </DraggableFormDialog>
    <CustomerQuotationDialog v-if="quotationVisible" v-model="quotationVisible" module="interpretation" :defer-save="deferSave"
      :projects="documentProjects" :draft-project="quotationProject" :draft="quotationDraft||context.quotation||quotationDefaults"
      @update:draft="quotationDraft=$event" @saved="refreshQuotationRevision" />
    <InterpretationStatementDialog v-if="statementVisible" v-model="statementVisible" :projects="documentProjects" />
  </span>
</template>
<script setup>
import CustomerQuotationDialog from './CustomerQuotationDialog.vue'
import InterpretationStatementDialog from './InterpretationStatementDialog.vue'
import ClientManagementLink from './ClientManagementLink.vue'
import CustomerFinanceModuleTabs from './CustomerFinanceModuleTabs.vue'
import {computed,ref,onBeforeUnmount,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import InterpretationFinanceFields from './InterpretationFinanceFields.vue'
import ReadonlyField from './ReadonlyField.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getInterpretationFinance,saveInterpretationFinance,getInterpretationFinanceHistory} from '@/api/interpretationCustomerFinance'
import {emptyInterpretationFinance,financeDraft,financeSummary,formatFinanceAmounts,interpretationCurrencies,interpretationFinancePayload,interpretationFinanceTotals} from '@/utils/interpretationCustomerFinance'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({
  scope:{type:String,default:'project'},targetId:{type:[String,Number],default:''},canWrite:Boolean,
  deferSave:Boolean, project:{type:Object,default:()=>({})}, pending:{type:Object,default:null},
})
const emit=defineEmits(['saved','update:pending'])
const canWriteClients=hasPermission('clients:write')
const financeModule=ref('interpretation')
const quotationVisible=ref(false),statementVisible=ref(false),quotationDraft=ref(null)
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),context=ref({}),draft=ref(null),body=ref(),form=ref(),history=ref([]),historyTotal=ref(0),historyPage=ref(1)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const activeDirections=computed(()=>props.deferSave ? props.project.directions||[] : context.value.directions||[])
const documentProjects=computed(()=>props.targetId?[{id:props.targetId,order_no:context.value.order_no,
  project_name:context.value.project_name,payload:context.value.payload}]:[])
const quotationProject=computed(()=>({orderNo:context.value.order_no,projectName:context.value.project_name,
  clientShortName:context.value.client_short_name,languagePair:activeDirections.value[0]?.label}))
const quotationDefaults=computed(()=>{
  if(!draft.value?.rates.length)return null
  const basis=draft.value.settlement.tax_basis
  return {client_name:props.project.clientFullName||context.value.client_short_name||'',notes:draft.value.settlement.customer_explanation,
    items:draft.value.rates.map(row=>({description:context.value.project_name||'口译服务',language_pair:row.direction,
      quantity:row.quantity,unit:row.unit,currency:row.currency,
      unit_price:basis==='legacy'?row.amount:basis==='incl_tax'?row.taxPrices.unitPriceInclTax:row.taxPrices.unitPriceExclTax}))}
})
let sequence=0
const original=ref('')
const signature=()=>JSON.stringify([draft.value,quotationDraft.value])
async function loadHistory(){
  if(!props.targetId)return
  const seq=sequence,page=historyPage.value
  try{
    const data=await getInterpretationFinanceHistory(props.scope,props.targetId,page)
    if(seq===sequence&&page===historyPage.value){history.value=data.items;historyTotal.value=data.total}
  }catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'调整记录加载失败')}
}
async function open(){
  financeModule.value='interpretation'
  const seq=++sequence
  visible.value=true;loading.value=true;error.value='';draft.value=null;history.value=[];historyTotal.value=0;historyPage.value=1
  clearFieldSearch()
  try{
    let data=props.targetId ? await getInterpretationFinance(props.scope,props.targetId) : {
      ready:true,revision:0,payload:emptyInterpretationFinance(),
    }
    if(props.deferSave){
      const project=props.project
      if(project.clientId && project.clientId!==data.client_id){
        try{
          const reference=await getInterpretationFinance('client',project.clientId)
          data={...data,reference_rates:reference.payload.rates,library_revision:reference.revision}
        }catch(e){
          if(e.response?.status!==403)throw e
          data={...data,reference_rates:[],library_revision:undefined}
        }
      }else if(!project.clientId){
        data={...data,reference_rates:[],library_revision:undefined}
      }
      data={...data,client_id:project.clientId,client_short_name:project.clientShortName,
        order_no:project.orderNo,project_name:project.projectName,project_status:project.projectStatus}
    }
    if(seq!==sequence)return
    context.value=data
    const payload=props.pending||data.payload
    const {revision,update_library,sync_confirmed,library_revision,library_client_id,quotation_draft,...fields}=payload
    quotationDraft.value=quotation_draft||null
    draft.value=financeDraft(fields)
    if(props.deferSave&&!props.pending&&!data.revision&&!draft.value.rates.length&&matchingRates().length)adopt()
    original.value=signature()
    if(!data.ready)error.value='口译财务数据表尚未初始化'
    if(props.targetId)void loadHistory()
  }catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'财务信息加载失败')}
  finally{if(seq===sequence)loading.value=false}
}
function matchingRates(){
  const directions=new Set(activeDirections.value.map(row=>row.label))
  return (context.value.reference_rates||[]).filter(row=>directions.has(row.direction))
}
function adopt(){
  const rates=matchingRates()
  if(!rates.length)return ElMessage.warning('客户参考价没有匹配的口译方向')
  draft.value.rates=financeDraft({...draft.value,rates}).rates
}
async function close(done){
  if(saving.value)return
  if(draft.value&&signature()!==original.value&&props.canWrite){
    try{await ElMessageBox.confirm('存在未保存的财务调整，确定关闭？','关闭财务表单')}catch{return}
  }
  sequence++
  if(typeof done==='function')done();else visible.value=false
}
async function save(syncToClient=false){
  if(saving.value||!props.canWrite||!await form.value?.validate().catch(()=>false))return
  if(syncToClient){
    try{await ElMessageBox.confirm(
      props.deferSave?'确认在保存项目时同步单价至客户管理？':'确认同步单价至客户管理？客户参考价变更会同步至仍沿用原价的项目。',
      '确认同步客户单价',{type:'warning',confirmButtonText:'确认同步',cancelButtonText:'取消'})}
    catch{return}
  }
  const payload={...interpretationFinancePayload(draft.value),revision:props.pending?.revision??context.value.revision,
    update_library:syncToClient,sync_confirmed:syncToClient,
    library_revision:syncToClient?context.value.library_revision:undefined}
  if(props.deferSave){
    if(syncToClient)payload.library_client_id=context.value.client_id
    if(quotationDraft.value)payload.quotation_draft=quotationDraft.value
    emit('update:pending',payload)
    original.value=signature()
    close()
    return
  }
  saving.value=true;error.value=''
  try{
    const data=await saveInterpretationFinance(props.scope,props.targetId,payload)
    context.value=data;draft.value=financeDraft(data.payload);original.value=signature();historyPage.value=1
    void loadHistory()
    emit('saved')
    ElMessage.success('财务调整已保存并记录')
  }catch(e){error.value=getLocalizedErrorMessage(e,'保存失败')}
  finally{saving.value=false}
}
async function refreshQuotationRevision(){
  const seq=sequence
  try{
    const data=await getInterpretationFinance(props.scope,props.targetId)
    if(seq!==sequence)return
    // A quotation-only save increments the shared version. Rebase only when the
    // prices and settlement the editor opened with are still current.
    if(JSON.stringify(data.payload)===JSON.stringify(context.value.payload)){
      context.value={...context.value,revision:data.revision,quotation:data.quotation}
      void loadHistory()
    }
    emit('saved')
  }catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'报价单已保存，刷新收费版本失败')}
}
watch(()=>props.targetId,()=>{sequence++;visible.value=false;quotationVisible.value=false;statementVisible.value=false;draft.value=null})
onBeforeUnmount(()=>sequence++)
</script>
<style scoped>
.finance-receipt{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;border:1px solid var(--el-border-color);padding:12px;margin-bottom:8px}.finance-receipt .el-date-editor{max-width:100%}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}:global(.interpretation-finance-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.interpretation-finance-dialog .el-dialog__header),:global(.interpretation-finance-dialog .el-dialog__footer){flex-shrink:0}:global(.interpretation-finance-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.interpretation-finance-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
