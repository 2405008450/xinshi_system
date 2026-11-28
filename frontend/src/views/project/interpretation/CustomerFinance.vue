<template>
  <el-card shadow="never">
    <template #header>
      <div class="heading">
        <strong>{{clientScope?'口译项目收费':'口译'}}</strong>
        <div class="heading-actions">
          <template v-if="canReadProjects">
            <el-button @click="openDocument('quotation')">报价单</el-button>
            <el-button @click="openDocument('statement')">对账单</el-button>
            <el-button @click="openInvoicePicker">发票</el-button><el-button @click="openSpecial">特殊结算</el-button><el-button @click="ledgerVisible=true">查账追账</el-button>
          </template>
          <TableColumnSettings v-model="selectedKeys" settings-key="interpretation-customer-finance" :columns="columns" @reset="resetColumns" />
        </div>
      </div>
    </template>
    <CustomerQuotationDialog v-if="quotationVisible" v-model="quotationVisible" module="interpretation" :projects="documentProjects" :query="queryParams()" @saved="saved" />
    <BusinessFinanceLedgerDialog @price="row=>openDocument('price',row)" @statement="row=>openDocument('statement',row)" @invoice="row=>openDocument('invoice',row)" v-if="ledgerVisible" v-model="ledgerVisible" module="interpretation" :query="queryParams()" />
    <DraggableFormDialog v-model="invoicePicker" title="发票 · 客户与结算项目" width="min(1000px, calc(100vw - 32px))" append-to-body destroy-on-close><BusinessFinanceScopePicker v-if="invoicePicker" v-model="invoiceTarget" :query="queryParams()" @select="row=>{invoiceOptions=row?[row]:[]}"/><template #footer><el-button @click="invoicePicker=false">取消</el-button><el-button :disabled="!invoiceTarget" type="primary" @click="chooseInvoice">打开发票窗口</el-button></template></DraggableFormDialog>
    <InterpretationStatementDialog v-if="statementVisible" v-model="statementVisible" :project-id="actionRow?.id" :projects="documentProjects" :query="queryParams()" :initial-mode="specialEntry?'special':undefined" />
    <InterpretationInvoiceDialog v-if="invoiceVisible" v-model="invoiceVisible" :project-id="actionRow?.id"
      :can-write="canWrite" @saved="saved" @statement="openDocument('statement',actionRow)" @price="openPrice(actionRow)" />
    <InterpretationFinanceEditor ref="financeEditor" :target-id="editorTarget" :can-write="canWrite" hide-trigger @saved="saved" />
    <AppForm data-auto-draft="off" :model="filters" inline @submit.prevent="search">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="订单号、项目名称、客户名称" clearable @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="客户经理"><el-select v-model="filters.manager" placeholder="选择或输入客户经理" @change="search"><el-option :label="`本人（${selfName}）`" value="self" /><el-option label="全部客户经理" value="all" /><el-option label="指定客户经理" value="name" /></el-select><FinanceManagerNameSelect v-if="filters.manager==='name'" v-model="filters.managerName" @change="search" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearAdvanced" @reset="reset">
          <div class="finance-advanced">
            <el-form-item label="金额"><el-checkbox v-model="filters.missingAmount" @change="search">计费金额待填写</el-checkbox></el-form-item>
          </div>
        </AdvancedFilterPopover>
      </el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border row-key="id">
      <el-table-column type="index" label="序号" width="65" :index="index=>(page-1)*10+index+1" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" show-sub-client :min-width="column.width">
        <template #header>
          <ConfiguredColumnHeaderFilter :definition="headerDefinitions[column.key]" :model-value="columnFilters[column.key]"
            @update:model-value="columnFilters[column.key]=$event" @change="search" @clear="search" />
        </template>
        <template #default="{row}">
          <el-select v-if="column.key==='settlement_mode'&&canWrite&&row.ready" :model-value="row.settlement_mode||'individual'"
            :disabled="settlementSaving.has(row.id)" :aria-label="`${row.order_no} 结算模式`" @change="changeSettlement(row,$event)">
            <el-option v-for="(label,value) in settlementModeLabels" :key="value" :label="label" :value="value"
              :disabled="value==='sub_client'&&!row.sub_client_id" />
          </el-select>
          <template v-else-if="['totals_excl_tax','totals_incl_tax'].includes(column.key)">
            <div v-for="currency in amountCurrencies(row,column.key)" :key="currency" class="finance-amount-cell">
              <strong>{{currency}}</strong><small>折扣前：{{baseAmount(row,currency,column.key)}}</small>
              <template v-if="canWrite&&row.ready"><label>折扣（%）<el-input-number :model-value="amountAdjustment(row,currency)[amountPrefix(column.key)+'_discount']" :min="1" :max="99" :precision="0" :controls="false" placeholder="01–99" :disabled="settlementSaving.has(row.id)" @change="value=>saveAmountCell(row,currency,amountPrefix(column.key)+'_discount',value)" /></label><label>调整后价格<el-input-number :model-value="amountAdjustment(row,currency)[amountPrefix(column.key)+'_amount']" :min="0" :precision="2" :controls="false" placeholder="选填，优先于折扣" :disabled="settlementSaving.has(row.id)" @change="value=>saveAmountCell(row,currency,amountPrefix(column.key)+'_amount',value)" /></label></template>
              <template v-else><small>折扣：{{amountAdjustment(row,currency)[amountPrefix(column.key)+'_discount']??'—'}}%</small><small>调整后价格：{{amountAdjustment(row,currency)[amountPrefix(column.key)+'_amount']??'—'}}</small></template>
              <strong>结算总价：{{row[column.key]?.[currency]??'待填写'}}</strong>
            </div>
          </template>
          <template v-else-if="column.key==='payment_status'"><span>{{cell(row,column.key)}}</span><el-button v-if="canWrite" link type="primary" @click="openPrice(row)">登记／修改付款</el-button></template>
          <template v-else-if="column.key==='rates'&&row.pricing_mode!=='fixed'"><span class="finance-text">{{financeSummary({rates:row.payload?.rates||[],has_overtime:row.payload?.has_overtime,overtime:row.payload?.overtime})}}</span><InlineInterpretationRates v-if="canWrite&&row.ready" :row="row" @saved="saved"/></template>
          <template v-else-if="['rates','workload'].includes(column.key)&&row.pricing_mode!=='fixed'&&row.payload?.rates?.length">
            <div v-for="(rate,index) in row.payload.rates" :key="index" class="finance-rate">
              <strong>{{rate.direction}}</strong>
              <span class="finance-text">{{column.key==='rates'?interpretationUnitPrice(rate):interpretationWorkload(rate)}}</span>
            </div>
          </template>
          <span v-else class="finance-text">{{cell(row,column.key)}}</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" title="口译客户财务详情"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="finance-detail"><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="column in columns" :key="column.key" :label="column.label" :client-row="row" show-sub-client><span class="finance-text">{{cell(row,column.key)}}</span></el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
      <el-table-column v-if="canReadProjects" label="操作" fixed="right" align="center" width="68">
        <template #default="{row}">
          <ProjectListRowActions :editable="false" :show-start-request="false"
            :extra-actions="financeRowActions(row)" @extra-command="handleRowAction(row,$event)" />
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <el-descriptions title="当前筛选金额小计" :column="3" border>
      <el-descriptions-item label="不含税总价"><span class="finance-text">{{formatFinanceAmounts(totalsExclTax)}}</span></el-descriptions-item>
      <el-descriptions-item label="含税总价"><span class="finance-text">{{formatFinanceAmounts(totalsInclTax)}}</span></el-descriptions-item>
      <el-descriptions-item label="计费合计"><span class="finance-text">{{formatFinanceAmounts(billingTotals)}}</span></el-descriptions-item>
    </el-descriptions>
    <p v-if="incomplete">{{incomplete}} 个项目尚未填写计费金额。</p>
  </el-card>
</template>
<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import {computed,nextTick,ref,reactive,onMounted,onBeforeUnmount,watch} from 'vue'
import {saveInterpretationFinance,getInterpretationFinancePage,saveInterpretationSettlementMode} from '@/api/interpretationCustomerFinance'
import BusinessFinanceScopePicker from '@/components/common/BusinessFinanceScopePicker.vue'
import InlineInterpretationRates from '@/components/common/InlineInterpretationRates.vue'
import InterpretationFinanceEditor from '@/components/common/InterpretationFinanceEditor.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import {useTableColumns} from '@/composables/useTableColumns'
import {translationSettlementModeLabels as settlementModeLabels} from '@/utils/settlementModes'
import {financeSummary,financeDraft,interpretationFinancePayload,interpretationFinanceTotals,formatFinanceAmounts,interpretationUnitPrice,interpretationWorkload} from '@/utils/interpretationCustomerFinance'
import {ElMessage} from 'element-plus'
import {getProjectStatusLabel,PROJECT_STATUS_OPTIONS} from '@/utils/projectStatus'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import FinanceManagerNameSelect from '@/components/common/FinanceManagerNameSelect.vue'
import CustomerQuotationDialog from '@/components/common/CustomerQuotationDialog.vue'
import BusinessFinanceLedgerDialog from '@/components/common/BusinessFinanceLedgerDialog.vue'
import InterpretationStatementDialog from '@/components/common/InterpretationStatementDialog.vue'
import InterpretationInvoiceDialog from '@/components/common/InterpretationInvoiceDialog.vue'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import {createFilterModel,resetFilterModel,serializeFieldFilters} from '@/utils/listFieldFilters'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
const emit=defineEmits(['saved'])
function saved(){emit('saved');void load()}
const props=defineProps({clientId:{type:[String,Number],default:''},clientScope:Boolean})
const columns=[
  {key:'order_no',label:'订单号',width:155},
  {key:'project_name',label:'项目名称',width:190},
  {key:'client_short_name',label:'客户简称',width:170},
  {key:'project_status',label:'项目状态',width:112},
  {key:'directions',label:'口译方向',width:155},
  {key:'workload',label:'工作量统计',width:155},
  {key:'pricing_mode',label:'计价方式',width:106},
  {key:'billing_month',label:'账单月份',width:105},
  {key:'rates',label:'单价',width:186},
  {key:'totals_excl_tax',label:'不含税总价',width:220},
  {key:'totals_incl_tax',label:'含税总价',width:220},
  {key:'settlement_mode',label:'结算模式',width:148},
  {key:'documents',label:'单据需求',width:121},
  {key:'payment_status',label:'付款状态',width:140},
  {key:'billing_totals',label:'项目计费金额',width:145},
  {key:'received_totals',label:'实际付款（各期累计）',width:155},
  {key:'payment_difference',label:'付款差额（实付－应付）',width:165},
  {key:'explanation',label:'说明',width:165},
  {key:'totals',label:'原总价（税口径未确认）',width:185},
  {key:'adjusted_totals',label:'调整后总价',width:145},
]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('interpretation-customer-finance',columns,
  ['order_no','project_name','client_short_name','project_status','directions','workload','pricing_mode','billing_month',
    'rates','totals_excl_tax','totals_incl_tax','settlement_mode','documents','payment_status','billing_totals','received_totals','payment_difference'],{
    legacyDefaultKeys:['order_no','project_name','client_short_name','project_status','directions','pricing_mode','billing_month',
      'settlement_mode','rates','totals_excl_tax','totals_incl_tax','billing_totals'],
  })
const visibleColumns=computed(()=>columns.filter(col=>isVisible(col.key)))
const canWrite=hasPermission('projects:write'),selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const canReadProjects=hasPermission('projects:read')||canWrite
const ledgerVisible=ref(false),invoicePicker=ref(false),invoiceTarget=ref(''),invoiceOptions=ref([]),invoiceSearching=ref(false),specialEntry=ref(false)
async function searchInvoiceProjects(keyword=''){invoiceSearching.value=true;try{invoiceOptions.value=(await getInterpretationFinancePage({...queryParams(),keyword,skip:0,limit:100})).items}catch(e){ElMessage.error(getLocalizedErrorMessage(e,'项目加载失败'))}finally{invoiceSearching.value=false}}
function openInvoicePicker(){invoiceOptions.value=[...rows.value];invoiceTarget.value='';invoicePicker.value=true}
function chooseInvoice(){actionRow.value=invoiceOptions.value.find(row=>row.id===invoiceTarget.value);invoicePicker.value=false;invoiceVisible.value=true}
function openSpecial(){actionRow.value=null;specialEntry.value=true;statementVisible.value=true}
const quotationVisible=ref(false),statementVisible=ref(false),invoiceVisible=ref(false)
const actionRow=ref(null),financeEditor=ref(null),editorTarget=ref('')
const totalsExclTax=ref({}),totalsInclTax=ref({}),billingTotals=ref({})
const pricingModes={time:'按时长计费',fixed:'固定收费'}
const advancedVisible=ref(false),settlementSaving=reactive(new Set())
const defaultAdvanced=()=>({missingAmount:false})
const filters=reactive({keyword:'',manager:props.clientScope?'all':'self',managerName:'',...defaultAdvanced()}),rows=ref([]),incomplete=ref(0),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
const advancedCount=computed(()=>Number(filters.missingAmount))
const documentProjects=computed(()=>actionRow.value?[actionRow.value]:rows.value)
function financeRowActions(row){
  const history={command:'history',label:'修改记录'}
  const mode=row.settlement_mode
  if(mode==='special')return [{command:'statement',label:'特殊结算对账单'},{command:'invoice',label:'特殊结算发票'},{command:'price',label:'价格与付款'},history]
  const labels={
    monthly:['合并对账单','合并结算发票'],
    sub_client:['子客户对账单','子客户结算发票'],
  }
  const [statement,invoice]=labels[mode]||['对账单','发票']
  return [
    {command:'price',label:canWrite?'价格与付款':'查看价格与付款'},
    {command:'quotation',label:'报价单'},
    {command:'statement',label:statement,disabled:!row.billing_month},
    {command:'invoice',label:invoice},
    history,
  ]
}
function openDocument(command,row=null){
  actionRow.value=row;specialEntry.value=false
  if(command==='quotation')quotationVisible.value=true
  if(command==='statement')statementVisible.value=true
}
async function openPrice(row,history=false){
  editorTarget.value=row.id
  await nextTick()
  if(editorTarget.value===row.id)void financeEditor.value?.open({history,snapshot:row})
}
function handleRowAction(row,command){
  if(command==='price'||command==='history')return openPrice(row,command==='history')
  if(command==='invoice'){
    actionRow.value=row
    invoiceVisible.value=true
    return
  }
  openDocument(command,row)
}
let sequence=0,controller,timer
function queryParams(){return {field_filters:serializeFieldFilters(columnFilters,headerFields),client_id:props.clientId||undefined,missing_amount:filters.missingAmount||undefined,only_mine:filters.manager==='self',client_manager:filters.manager==='name'?filters.managerName:undefined}}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getInterpretationFinancePage({...queryParams(),keyword:filters.keyword,skip:(page.value-1)*10,limit:10},controller.signal);if(seq===sequence){totalsExclTax.value=data.totals_excl_tax||{};totalsInclTax.value=data.totals_incl_tax||{};billingTotals.value=data.billing_totals||{};rows.value=data.items;total.value=data.total;incomplete.value=data.incomplete}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'口译财务加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function clearAdvanced(){Object.assign(filters,defaultAdvanced());search()}
function reset(){resetFilterModel(columnFilters,headerFields);Object.assign(filters,defaultAdvanced());filters.keyword='';filters.manager=props.clientScope?'all':'self';filters.managerName='';search()}
async function changeSettlement(row,mode){
  if(settlementSaving.has(row.id)||mode===row.settlement_mode)return
  settlementSaving.add(row.id)
  try{
    const data=await saveInterpretationSettlementMode(row.id,{mode,revision:row.revision})
    const current=rows.value.find(item=>item.id===row.id)
    if(current)Object.assign(current,{settlement_mode:data.settlement_mode,revision:data.revision,payload:data.payload})
    saved()
    ElMessage.success('结算模式已保存')
  }catch(e){
    ElMessage.error(getLocalizedErrorMessage(e,'结算模式保存失败'))
    void load()
  }finally{settlementSaving.delete(row.id)}
}
const amountPrefix=key=>key==='totals_incl_tax'?'incl':'excl'
const amountAdjustment=(row,currency)=>(row.payload?.settlement_adjustments||[]).find(item=>item.currency===currency)||{}
function amountCurrencies(row,key){const result=new Set([...Object.keys(row[key]||{}),...(row.payload?.settlement_adjustments||[]).map(item=>item.currency)]);return result.size?[...result]:['CNY']}
function baseAmount(row,currency,key){return interpretationFinanceTotals(financeDraft(row.payload),key==='totals_incl_tax'?'incl_tax':'excl_tax',false,false)[currency]??'待填写'}
async function saveAmountCell(row,currency,key,value){if(settlementSaving.has(row.id))return;const data=financeDraft(row.payload);const list=data.settlement_adjustments;let entry=list.find(item=>item.currency===currency);if(!entry){entry={currency};list.push(entry)}if(value==null||value==='')delete entry[key];else entry[key]=value;if(Object.keys(entry).length===1)list.splice(list.indexOf(entry),1);const payload=interpretationFinancePayload(data);const fields=['rates','has_overtime','overtime','adjusted_totals','fixed_totals','settlement_adjustments','explanation','settlement'];settlementSaving.add(row.id);try{const saved=await saveInterpretationFinance('project',row.id,{revision:row.revision,...Object.fromEntries(fields.map(field=>[field,payload[field]]))});Object.assign(row,saved);ElMessage.success('金额已保存并记录');emit('saved');void load()}catch(e){ElMessage.error(getLocalizedErrorMessage(e,'金额保存失败'));void load()}finally{settlementSaving.delete(row.id)}}
const paymentStatus={unrecorded:'未付款',deposit:'已付定金',partial:'已付进度款',full:'已付全款（含尾款）'}
const enumOptions={
  project_status:PROJECT_STATUS_OPTIONS.interpretation,
  pricing_mode:Object.entries(pricingModes).map(([value,label])=>({value,label})),
  settlement_mode:Object.entries(settlementModeLabels).map(([value,label])=>({value,label})),
  payment_status:Object.entries(paymentStatus).map(([value,label])=>({value,label})),
  documents:[{value:'quotation',label:'需报价单'},{value:'invoice',label:'需发票'},{value:'none',label:'均未勾选'}],
}
const amountFields=new Set(['totals_excl_tax','totals_incl_tax','billing_totals','totals','adjusted_totals','received_totals','payment_difference'])
const headerFields=columns.map(column=>({
  key:column.key,label:column.label,
  type:enumOptions[column.key]?'select':amountFields.has(column.key)?'number-range':'text',
  options:enumOptions[column.key],precision:amountFields.has(column.key)?2:undefined,
  headerWidth:amountFields.has(column.key)?300:260,
  placeholder:column.key==='billing_month'?'如 2026-11':column.key==='rates'?'方向、币种、单价或单位':
    column.key==='workload'?'方向、数量或计时单位':undefined,
}))
const headerDefinitions=Object.fromEntries(headerFields.map(field=>[field.key,field]))
const columnFilters=reactive(createFilterModel(headerFields))

function cell(row,key){
  if(key==='project_status')return getProjectStatusLabel('interpretation',row[key])
  if(key==='directions')return row.directions.map(x=>x.label).join('\n')||'-'
  if(key==='pricing_mode')return pricingModes[row.pricing_mode||'time']
  if(key==='settlement_mode')return settlementModeLabels[row.settlement_mode||'individual']
  if(key==='payment_status')return paymentStatus[row.payload?.settlement?.payment_status||'unrecorded']
  if(key==='documents')return [row.payload?.settlement?.quotation_required?'需报价单':'',row.payload?.settlement?.invoice_required?'需发票':''].filter(Boolean).join('、')||'—'
  if(key==='rates'||key==='workload'){
    if(row.pricing_mode==='fixed')return '固定收费'
    const format=key==='rates'?interpretationUnitPrice:interpretationWorkload
    return key==='rates'?financeSummary({rates:row.payload?.rates||[],has_overtime:row.payload?.has_overtime,overtime:row.payload?.overtime}):(row.payload?.rates||[]).map(rate=>`${rate.direction}\n${format(rate)}`).join('\n')||'待填写'
  }
  if(['totals','adjusted_totals','totals_excl_tax','totals_incl_tax','billing_totals','received_totals','payment_difference'].includes(key))return formatFinanceAmounts(row[key])
  if(key==='explanation')return row.payload.explanation||'-'
  return row[key]||'-'
}
onMounted(()=>void load())
watch(()=>props.clientId,search)
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
useProjectStatusSync('interpretation',rows,{field:'project_status',onChanged:()=>{if(!loading.value)void load()}})
</script>
<style scoped>
.heading,.heading-actions{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}.heading-actions>.el-button{margin:0}.finance-rate{display:grid;gap:3px;line-height:1.45}.finance-rate+.finance-rate{margin-top:6px;padding-top:6px;border-top:1px solid var(--el-border-color-lighter)}.finance-rate strong{font-size:12px}.finance-advanced{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 12px}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}.finance-detail{max-height:560px;overflow-y:auto}.el-pagination{margin:16px 0}.el-select{width:100%}.finance-advanced :deep(.el-form-item){margin-right:0}p{font-size:12px;color:#64748b}
</style>

<style scoped>.finance-amount-cell{display:grid;gap:5px;margin-bottom:8px}.finance-amount-cell label{display:grid;grid-template-columns:80px minmax(0,1fr);align-items:center;font-size:12px}.finance-amount-cell small{color:var(--el-text-color-secondary)}.finance-amount-cell :deep(.el-input-number){width:100%}</style>
