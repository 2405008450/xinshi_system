<template>
  <section class="statement-tax-preference" data-dialog-field-search-label="对账单设置">
    <el-checkbox :model-value="preference.tax_included" :disabled="disabled" @change="persist({tax_included:$event})">单价含税</el-checkbox>
    <span>对账单采用客户选择的税口径；未勾选时标注“不含税”。</span>
    <div class="statement-document-settings">
      <label>对账单主体
        <el-select :model-value="preference.statement_subject_key || 'default'" aria-label="对账单主体" :disabled="disabled" @change="persist({statement_subject_key:$event==='default'?null:$event})">
          <el-option label="系统默认" value="default" /><el-option label="广州总公司" value="guangzhou" /><el-option label="深圳分公司" value="shenzhen" /><el-option label="上海分公司" value="shanghai" />
        </el-select>
      </label>
      <label>是否需对账单
        <el-select :model-value="preference.statement_default" aria-label="是否需对账单" :disabled="disabled" @change="persist({statement_default:$event})">
          <el-option label="需" value="required" /><el-option label="无需" value="not_required" /><el-option label="未知" value="unknown" />
        </el-select>
      </label>
      <label>是否需报价单
        <el-select :model-value="preference.quotation_required ?? 'default'" aria-label="是否需报价单" :disabled="disabled" @change="saveRequirement('quotation_required',$event)">
          <el-option label="需" :value="true" /><el-option label="无需" :value="false" /><el-option label="未设置" value="default" />
        </el-select>
      </label>
      <label>是否需发票
        <el-select :model-value="preference.invoice_required ?? 'default'" aria-label="是否需发票" :disabled="disabled" @change="saveRequirement('invoice_required',$event)">
          <el-option label="需" :value="true" /><el-option label="无需" :value="false" /><el-option label="按项目计费口径" value="default" />
        </el-select>
      </label>
    </div>
    <div class="statement-default-setting" data-dialog-field-search-label="结算模式">
      <div>结算模式</div>
      <el-radio-group :model-value="preference.payment_method==='statement'?'monthly':preference.payment_method" aria-label="结算模式" :disabled="disabled" @update:model-value="persist({payment_method:$event})">
        <el-radio value="individual">{{translationSettlementModeLabels.individual}}</el-radio>
        <el-radio value="monthly">{{translationSettlementModeLabels.monthly}}</el-radio>
      </el-radio-group>
      <el-button v-if="preference.payment_method" link :disabled="disabled" @click="persist({payment_method:null})">恢复自动判断</el-button>
      <div><small>保存后同步至客户关联订单。订单差异按单号和版本记录在下方。</small></div>
    </div>
    <details v-if="clientId" @toggle="historyOpen=$event.target.open;historyOpen && loadHistory()">
      <summary>单据需求与结算模式修改记录</summary>
      <el-alert v-if="historyError" :title="historyError" type="error" :closable="false" />
      <el-table v-loading="historyLoading" :data="history.items" empty-text="暂无修改记录">
        <el-table-column label="时间" min-width="150"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column>
        <el-table-column prop="actor_name" label="操作人" min-width="90" />
        <el-table-column label="来源" min-width="150"><template #default="{row}">{{row.order_no?`${row.order_no} · 第${row.revision}版`:row.origin==='document_defaults_project'?'价格与付款':'客户管理'}}</template></el-table-column>
        <el-table-column label="修改前 → 修改后" min-width="240">
          <template #default="{row}"><div v-for="(value,field) in row.after" :key="field">{{historyFields[field]}}：{{historyValue(row.before[field])}} → {{historyValue(value)}}</div></template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="history.total>10" v-model:current-page="historyPage" :page-size="10" :total="history.total" layout="prev,pager,next" @current-change="loadHistory" />
    </details>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
  </section>
</template>
<script setup>
import { settlementModeLabels, translationSettlementModeLabels } from '@/utils/settlementModes'
import {computed,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {getStatementPreference,saveStatementPreference,getStatementPreferenceHistory} from '@/api/customerStatements'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {connectInvoiceParties,notifyInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const emptyPreference=()=>({tax_included:false,statement_default:'unknown',revision:0})
const preference=ref(emptyPreference()),loading=ref(false),saving=ref(false),error=ref('')
const disabled=computed(()=>!props.clientId||!props.canWrite||loading.value||saving.value||!!error.value)
const history=ref({items:[],total:0}),historyPage=ref(1),historyError=ref(''),historyLoading=ref(false),historyOpen=ref(false)
const historyFields={statement_default:'对账单',quotation_required:'报价单',invoice_required:'发票',payment_method:'结算模式'}
const historyLabels={required:'需',not_required:'无需',true:'需',false:'无需',...settlementModeLabels}
const historyValue=value=>historyLabels[value]||'未设置'
let historySequence=0
async function loadHistory(){
  const current=++historySequence,id=props.clientId
  historyLoading.value=true
  historyError.value=''
  try{
    const data=await getStatementPreferenceHistory(id,historyPage.value)
    if(current===historySequence&&id===props.clientId)history.value=data
  }catch(e){
    if(current===historySequence&&id===props.clientId)historyError.value=getLocalizedErrorMessage(e,'修改记录加载失败')
  }finally{if(current===historySequence)historyLoading.value=false}
}
let sequence=0,controller
async function load(){
  controller?.abort()
  const seq=++sequence
  preference.value=emptyPreference()
  error.value=''
  saving.value=false
  loading.value=!!props.clientId
  if(!props.clientId)return
  controller=new AbortController()
  try{
    const data=await getStatementPreference(props.clientId,{signal:controller.signal})
    if(seq===sequence)preference.value=data
  }catch(e){
    if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户财务设置加载失败')
  }finally{if(seq===sequence)loading.value=false}
}
function saveRequirement(field,value){return persist({[field]:value==='default'?null:value})}
async function persist(patch){
  if(disabled.value)return
  const id=props.clientId,seq=sequence
  saving.value=true
  try{
    const {revision,tax_included}=preference.value
    const data=await saveStatementPreference(id,{revision,tax_included,...patch})
    if(seq===sequence){
      preference.value=data
      notifyInvoiceParties({kind:'customer-statement-settings',clientId:String(id)})
      historyPage.value=1
      if(historyOpen.value)void loadHistory()
      window.dispatchEvent(new CustomEvent('customer-statement-preference-saved',{detail:{clientId:id}}))
    }
  }catch(e){
    if(seq===sequence)error.value=getLocalizedErrorMessage(e,'客户财务设置保存失败，请重新加载')
  }finally{if(seq===sequence)saving.value=false}
}
watch(()=>props.clientId,load,{immediate:true})
function refreshAfterProjectSync(event){
  if(event.detail?.clientId===props.clientId&&!saving.value){void load();if(historyOpen.value)void loadHistory()}
}
function refreshOrderHistory(event){
  if(historyOpen.value&&event.detail?.clientId===String(props.clientId))void loadHistory()
}
function automaticSettings(event){if(['translation-finance','customer-statement-settings','statement-subject'].includes(event.detail?.kind))refreshAfterProjectSync(event)}
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,automaticSettings)
onBeforeUnmount(()=>window.removeEventListener(invoicePartiesEvent,automaticSettings))
onMounted(()=>{
  window.addEventListener('customer-statement-preference-saved',refreshAfterProjectSync)
  window.addEventListener('customer-order-finance-saved',refreshOrderHistory)
})
onBeforeUnmount(()=>{sequence++;controller?.abort();window.removeEventListener('customer-statement-preference-saved',refreshAfterProjectSync);window.removeEventListener('customer-order-finance-saved',refreshOrderHistory)})
</script>
<style scoped>
.statement-document-settings{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}.statement-document-settings label{display:grid;gap:4px;min-width:160px}.statement-default-setting{margin-top:12px}.statement-default-setting small{color:var(--el-text-color-secondary)}.statement-tax-preference>span{font-size:12px;color:var(--el-text-color-secondary);margin-left:12px}.el-alert{margin-top:8px}
</style>
