<template>
  <span>
    <el-button v-if="!hideTrigger" :disabled="!targetId&&!deferSave" :link="scope==='project'&&!deferSave" type="primary" @click="open()">{{scope==='client'?'口译参考价及调整记录':'价格与收费'}}</el-button>
    <DraggableFormDialog v-model="visible" append-to-body class="interpretation-finance-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" :before-close="close" :close-on-click-modal="false">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="scope==='client'?'客户口译参考价':`${historyOnly?'修改记录':'价格与收费'}${context.order_no?' · '+context.order_no:''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body" v-loading="loading||saving">
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <el-button v-if="loadFailed" link type="primary" @click="open({history:historyOnly})">重新加载财务信息</el-button>
        <CustomerFinanceModuleTabs v-model="financeModule" module="interpretation" :enabled="scope==='project'" :client-id="context.client_id"><template #interpretation>
        <AppForm v-if="draft&&!loading&&!historyOnly" ref="form" :model="draft" label-position="top" :disabled="saving||!canWrite||!context.ready">
          <section v-if="scope==='project'" class="finance-region finance-identifiers"
            data-dialog-field-search-group data-dialog-field-search-group-title="订单信息">
            <el-form-item label="订单号"><ReadonlyField :model-value="context.order_no||''" source="auto" placeholder="保存后自动生成" /></el-form-item>
            <el-form-item label="项目名称"><ReadonlyField :model-value="context.project_name||'-'" source="auto" /></el-form-item>
            <el-form-item label="客户简称"><ClientManagementLink :value="context.client_short_name" :row="context" show-sub-client /></el-form-item>
            <el-form-item label="项目状态"><ReadonlyField :model-value="getProjectStatusLabel('interpretation',context.project_status)" source="auto" /></el-form-item>
          </section>
          <section v-if="scope==='project'" class="finance-region" data-dialog-field-search-group data-dialog-field-search-group-title="计价与结算">
            <h3>计价与结算</h3>
            <el-form-item label="结算模式" prop="settlement.payment_method" :rules="[{validator:validateSettlement,trigger:'change'}]">
              <div class="settlement-options">
                <el-radio-group v-model="draft.settlement.payment_method" aria-label="结算模式">
                  <el-radio v-for="(label, mode) in settlementModeLabels" :key="mode" :value="mode"
                    :disabled="mode==='sub_client'&&!context.sub_client_id">{{label}}</el-radio>
                </el-radio-group>
                <small>{{settlementHints[draft.settlement.payment_method]}}</small>
              </div>
            </el-form-item>
            <el-form-item label="计价方式">
              <el-radio-group v-model="draft.settlement.pricing_mode" aria-label="计价方式">
                <el-radio-button value="time">按时长计费</el-radio-button>
                <el-radio-button value="fixed">固定收费</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="账单月份"><el-date-picker v-model="draft.settlement.billing_month" type="month" value-format="YYYY-MM" :placeholder="context.billing_month||'默认按订单日期'" /></el-form-item>
            <el-form-item label="计费税口径"><el-select v-model="draft.settlement.tax_basis" style="width:200px"><el-option label="不含税" value="excl_tax" /><el-option label="含税" value="incl_tax" /><el-option label="税口径未确认" value="legacy" /></el-select></el-form-item>
          </section>
            <section v-if="scope==='project'" class="finance-region finance-documents" data-dialog-field-search-group data-dialog-field-search-group-title="单据需求">
            <h3>单据需求</h3>
            <el-form-item label="单据需求"><el-checkbox v-model="draft.settlement.quotation_required">需报价单</el-checkbox><el-checkbox v-model="draft.settlement.invoice_required">需发票</el-checkbox></el-form-item>
            <el-form-item label="单据">
              <el-button @click="quotationVisible=true">报价单</el-button>
              <el-button :disabled="!targetId" @click="statementVisible=true">对账单</el-button>
            </el-form-item>
            </section>
          <div v-if="scope==='project'&&draft.settlement.pricing_mode==='time'" class="finance-reference-actions">
            <el-form-item label="客户参考价"><el-button :disabled="!context.reference_rates?.length" @click="adopt">采用匹配方向的客户参考价</el-button></el-form-item>
            <el-form-item v-if="canWriteClients&&context.client_id&&context.library_revision!=null" label="同步客户参考价">
              <el-button @click="save(true)">保存并同步单价至客户信息…</el-button>
            </el-form-item>
          </div>
          <InterpretationFinanceFields v-model="draft" :directions="activeDirections" :reference-only="scope==='client'" />
          <template v-if="scope==='project'">
            <el-form-item label="客户说明"><el-input v-model="draft.settlement.customer_explanation" type="textarea" :rows="2" maxlength="5000" /></el-form-item>
            <section class="finance-region" data-dialog-field-search-group data-dialog-field-search-group-title="结算金额">
              <h3>结算金额</h3>
              <div class="finance-identifiers">
                <el-form-item label="不含税结算总价"><ReadonlyField type="textarea" autosize :model-value="formatFinanceAmounts(interpretationFinanceTotals(draft,'excl_tax'))" source="auto" /></el-form-item>
                <el-form-item label="含税结算总价"><ReadonlyField type="textarea" autosize :model-value="formatFinanceAmounts(interpretationFinanceTotals(draft,'incl_tax'))" source="auto" /></el-form-item>
                <el-form-item label="当前计费合计"><ReadonlyField type="textarea" autosize :model-value="formatFinanceAmounts(interpretationFinanceTotals(draft))" source="auto" /></el-form-item>
              </div>
              <p>结算金额已包含加班费和总价调整，计费合计按上方的计费税口径取值。</p>
            </section>
            <section class="finance-region" data-dialog-field-search-group data-dialog-field-search-group-title="收款情况">
            <h3>收款情况</h3>
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
            </section>
            <p v-if="deferSave">收费和报价单随项目保存，对账单使用已保存的收费。</p>
          </template>
        </AppForm>
        <p v-if="scope==='project'&&!historyOnly">对应税口径未填写的项目不参与该口径合计；未填写不代表零税率。</p>

        <template v-if="scope==='client' && visible">
          <p v-if="signature()!==original" class="finance-text">请先保存或放弃当前修改，再引入项目单价。</p>
          <CustomerRateDifferences module="interpretation" :client-id="targetId" :revision="context.revision||0" :disabled="saving || signature()!==original" @saved="open" />
        </template>
        <section v-if="targetId" :aria-busy="historyLoading">
          <h4>调整记录（{{historyTotal}}）</h4>
          <p v-if="historyLoading">正在加载调整记录…</p>
          <el-alert v-else-if="historyError" :title="historyError" type="warning" :closable="false">
            <el-button link type="primary" @click="loadHistory">重新加载调整记录</el-button>
          </el-alert>
          <el-collapse><el-collapse-item v-for="item in history" :key="item.id" :title="`第${item.revision}次 · ${item.actor_name} · ${formatTime(item.created_at)}`"><el-descriptions :column="1" border><el-descriptions-item label="调整前"><span class="finance-text">{{financeSummary(item.before)}}</span></el-descriptions-item><el-descriptions-item label="调整后"><span class="finance-text">{{financeSummary(item.after)}}</span></el-descriptions-item></el-descriptions></el-collapse-item></el-collapse>
          <el-pagination v-model:current-page="historyPage" :total="historyTotal" :page-size="10" layout="total, prev, pager, next" @current-change="loadHistory" />
        </section>
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button v-if="canWrite&&!historyOnly&&(scope==='client'||financeModule==='interpretation')" type="primary" :disabled="loading||!draft||!context.ready" :loading="saving" @click="save()">{{deferSave?'应用到项目':'保存'}}</el-button></template>
    </DraggableFormDialog>
    <CustomerQuotationDialog v-if="quotationVisible" v-model="quotationVisible" module="interpretation" :defer-save="deferSave"
      :projects="documentProjects" :draft-project="quotationProject" :draft="quotationDraft||context.quotation||quotationDefaults"
      @update:draft="quotationDraft=$event" @saved="refreshQuotationRevision" />
    <InterpretationStatementDialog v-if="statementVisible" v-model="statementVisible" :projects="documentProjects" />
  </span>
</template>
<script setup>
import { translationSettlementModeLabels as settlementModeLabels } from '@/utils/settlementModes'
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
  deferSave:Boolean, hideTrigger:Boolean, project:{type:Object,default:()=>({})}, pending:{type:Object,default:null},
})
const emit=defineEmits(['saved','update:pending'])
const canWriteClients=hasPermission('clients:write')
const financeModule=ref('interpretation')
const historyOnly=ref(false)
const settlementHints={
  individual:'每个项目单独结算。',
  monthly:'同一客户下采用本模式的同期项目合并结算。',
  sub_client:'同一子客户下采用本模式的同期项目合并结算。',
  special:'该项目单独对账，可设置专用账单月份、计费口径和发票需求。',
}
function validateSettlement(_rule,value,done){
  done(value==='sub_client'&&!context.value.sub_client_id?new Error('请先关联子客户，或改用其他结算模式'):undefined)
}
const quotationVisible=ref(false),statementVisible=ref(false),quotationDraft=ref(null)
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),context=ref({}),draft=ref(null),body=ref(),form=ref(),history=ref([]),historyTotal=ref(0),historyPage=ref(1)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const activeDirections=computed(()=>props.deferSave ? props.project.directions||[] : context.value.directions||[])
const documentProjects=computed(()=>props.targetId?[{id:props.targetId,order_no:context.value.order_no,
  project_name:context.value.project_name,billing_month:context.value.billing_month,settlement_mode:context.value.settlement_mode,payload:context.value.payload}]:[])
const quotationProject=computed(()=>({orderNo:context.value.order_no,projectName:context.value.project_name,
  clientShortName:context.value.client_short_name,languagePair:activeDirections.value[0]?.label}))
const quotationDefaults=computed(()=>{
  if(!draft.value)return null
  const basis=draft.value.settlement.tax_basis
  const fixed=draft.value.settlement.pricing_mode==='fixed'
  const rows=fixed?draft.value.fixed_totals:draft.value.rates
  if(!rows.length)return null
  return {client_name:props.project.clientFullName||context.value.client_short_name||'',notes:draft.value.settlement.customer_explanation,
    items:rows.map(row=>{
      const key=(fixed?'total':'unitPrice')+(basis==='incl_tax'?'InclTax':'ExclTax')
      return {description:context.value.project_name||'口译服务',language_pair:row.direction,
        quantity:fixed?1:row.quantity,unit:fixed?'项':row.unit,currency:row.currency,
        unit_price:basis==='legacy'?row.amount:row.taxPrices?.[key]}
    })}
})
let sequence=0
let detailRequest,historyRequest
const loadFailed=ref(false),historyLoading=ref(false),historyError=ref('')
const original=ref('')
const signature=()=>JSON.stringify([draft.value,quotationDraft.value])
function stopLoading(){
  sequence++
  detailRequest?.abort()
  historyRequest?.abort()
  loading.value=false
  historyLoading.value=false
}
async function loadHistory(){
  if(!visible.value||!props.targetId)return
  historyRequest?.abort()
  const request=historyRequest=new AbortController()
  const page=historyPage.value
  historyLoading.value=true
  historyError.value=''
  try{
    const data=await getInterpretationFinanceHistory(props.scope,props.targetId,page,request.signal)
    if(!request.signal.aborted){history.value=data.items;historyTotal.value=data.total}
  }catch(e){if(!request.signal.aborted)historyError.value=getLocalizedErrorMessage(e,'调整记录加载失败')}
  finally{if(!request.signal.aborted)historyLoading.value=false}
}
async function open({history:showHistory=false,snapshot}={}){
  stopLoading()
  const seq=sequence
  const request=detailRequest=new AbortController()
  const target=props.targetId
  historyOnly.value=showHistory
  financeModule.value='interpretation'
  visible.value=true;loading.value=true;loadFailed.value=false;error.value='';historyError.value=''
  context.value={};draft.value=null;quotationDraft.value=null;history.value=[];historyTotal.value=0;historyPage.value=1
  try{
    clearFieldSearch()
    // The finance list includes the full pricing payload and optimistic-lock revision.
    // Detach it from the list's live synchronization before using it in an editor.
    const local=props.scope==='project'&&!props.deferSave&&snapshot?.id===target&&typeof snapshot.ready==='boolean'&&Number.isInteger(snapshot.revision)&&snapshot.payload
    let data=local ? JSON.parse(JSON.stringify(snapshot)) : target ? await getInterpretationFinance(props.scope,target,request.signal) : {
      ready:true,revision:0,payload:emptyInterpretationFinance(),
    }
    if(props.deferSave){
      const project=props.project
      if(project.clientId && project.clientId!==data.client_id){
        try{
          const reference=await getInterpretationFinance('client',project.clientId,request.signal)
          data={...data,reference_rates:reference.payload.rates,library_revision:reference.revision}
        }catch(e){
          if(e.response?.status!==403)throw e
          data={...data,reference_rates:[],library_revision:undefined}
        }
      }else if(!project.clientId){
        data={...data,reference_rates:[],library_revision:undefined}
      }
      data={...data,client_id:project.clientId,sub_client_id:project.subClientId,client_short_name:project.clientShortName,
        parent_client_short_name:project.parentClientShortName,sub_client_name:project.subClientName,
        order_no:project.orderNo,project_name:project.projectName,project_status:project.projectStatus}
    }
    if(seq!==sequence)return
    context.value=data
    const payload=props.pending||data.payload
    const {revision,update_library,sync_confirmed,library_revision,library_client_id,quotation_draft,...fields}=payload
    quotationDraft.value=quotation_draft||null
    draft.value=financeDraft(fields)
    if(!props.pending&&!data.revision&&props.scope==='project'&&!draft.value.rates.some(rate=>rate.taxPrices.unitPriceExclTax==null&&rate.taxPrices.unitPriceInclTax==null)){
      draft.value.settlement.tax_basis=draft.value.rates.length&&draft.value.rates.every(rate=>rate.taxPrices.unitPriceExclTax==null)?'incl_tax':'excl_tax'
    }
    if(props.deferSave&&!props.pending&&!data.revision&&!draft.value.rates.length&&matchingRates().length)adopt()
    original.value=signature()
    if(!data.ready)error.value='口译财务数据表尚未初始化'
    if(target)void loadHistory()
  }catch(e){if(seq===sequence){loadFailed.value=true;error.value=getLocalizedErrorMessage(e,'财务信息加载失败')}}
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
  stopLoading()
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
  const fixed=draft.value.settlement.pricing_mode==='fixed'
  const savedFields=financeDraft(props.pending||context.value.payload)
  const activeFields=fixed?{...draft.value,rates:savedFields.rates,has_overtime:savedFields.has_overtime,
    overtime:savedFields.overtime,adjusted_totals:savedFields.adjusted_totals}:{...draft.value,fixed_totals:savedFields.fixed_totals}
  const payload={...interpretationFinancePayload(activeFields),revision:props.pending?.revision??context.value.revision,
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
watch(()=>props.targetId,()=>{stopLoading();visible.value=false;quotationVisible.value=false;statementVisible.value=false;draft.value=null})
onBeforeUnmount(stopLoading)
defineExpose({open})
</script>
<style scoped>
.finance-region{margin:16px 0;padding:14px;border:1px solid var(--el-border-color);border-radius:8px}.finance-identifiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 12px}.finance-reference-actions{display:flex;flex-wrap:wrap;gap:0 12px}.finance-documents{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:20px}.finance-documents h3{width:100%}.finance-region h3{margin:0 0 12px}.settlement-options{display:grid}.settlement-options small{color:var(--el-text-color-secondary)}.finance-receipt{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;border:1px solid var(--el-border-color);padding:12px;margin-bottom:8px}.finance-receipt .el-date-editor{max-width:100%}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}:global(.interpretation-finance-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.interpretation-finance-dialog .el-dialog__header),:global(.interpretation-finance-dialog .el-dialog__footer){flex-shrink:0}:global(.interpretation-finance-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.interpretation-finance-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
