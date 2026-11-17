<template>
  <el-card shadow="never">
    <template #header>
      <div class="heading">
        <strong>{{clientScope?'口译项目收费':'口译'}}</strong>
        <div class="heading-actions">
          <template v-if="canReadProjects">
            <el-button @click="openDocument('quotation')">报价单</el-button>
            <el-button @click="openDocument('statement')">对账单</el-button>
          </template>
          <TableColumnSettings v-model="selectedKeys" settings-key="interpretation-customer-finance" :columns="columns" @reset="resetColumns" />
        </div>
      </div>
    </template>
    <CustomerQuotationDialog v-if="quotationVisible" v-model="quotationVisible" module="interpretation" :projects="documentProjects" :query="queryParams()" @saved="saved" />
    <InterpretationStatementDialog v-if="statementVisible" v-model="statementVisible" :projects="documentProjects" :query="queryParams()" />
    <InterpretationInvoiceDialog v-if="invoiceVisible" v-model="invoiceVisible" :project-id="actionRow?.id"
      :can-write="canWrite" @saved="saved" @statement="openDocument('statement',actionRow)" @price="openPrice(actionRow)" />
    <InterpretationFinanceEditor ref="financeEditor" :target-id="editorTarget" :can-write="canWrite" hide-trigger @saved="saved" />
    <AppForm data-auto-draft="off" :model="filters" inline @submit.prevent="search">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="订单号、项目名称、客户名称" clearable @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="账单月份"><el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" placeholder="全部月份" @change="search" /></el-form-item>
      <el-form-item label="客户经理"><el-select v-model="filters.manager" placeholder="选择或输入客户经理" @change="search"><el-option :label="`本人（${selfName}）`" value="self" /><el-option label="全部客户经理" value="all" /><el-option label="指定客户经理" value="name" /></el-select><FinanceManagerNameSelect v-if="filters.manager==='name'" v-model="filters.managerName" @change="search" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearAdvanced" @reset="reset">
          <div class="finance-advanced">
            <el-form-item label="计价方式"><el-select v-model="filters.pricing" clearable placeholder="全部" @change="search">
              <el-option v-for="(label,value) in pricingModes" :key="value" :label="label" :value="value" />
            </el-select></el-form-item>
            <el-form-item label="结算模式"><el-select v-model="filters.settlement" clearable placeholder="全部" @change="search">
              <el-option v-for="(label,value) in settlementModeLabels" :key="value" :label="label" :value="value" />
            </el-select></el-form-item>
            <el-form-item label="收款状态"><el-select v-model="filters.paymentStatus" clearable placeholder="全部" @change="search">
              <el-option v-for="(label,value) in paymentStatus" :key="value" :label="label" :value="value" />
            </el-select></el-form-item>
            <el-form-item label="金额"><el-checkbox v-model="filters.missingAmount" @change="search">计费金额待填写</el-checkbox></el-form-item>
          </div>
        </AdvancedFilterPopover>
      </el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border row-key="id">
      <el-table-column type="index" label="序号" width="65" :index="index=>(page-1)*10+index+1" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" show-sub-client :min-width="column.width">
        <template #default="{row}">
          <el-select v-if="column.key==='settlement_mode'&&canWrite&&row.ready" :model-value="row.settlement_mode||'individual'"
            :disabled="settlementSaving.has(row.id)" :aria-label="`${row.order_no} 结算模式`" @change="changeSettlement(row,$event)">
            <el-option v-for="(label,value) in settlementModeLabels" :key="value" :label="label" :value="value"
              :disabled="value==='sub_client'&&!row.sub_client_id" />
          </el-select>
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
import {computed,nextTick,ref,reactive,onMounted,onBeforeUnmount,onActivated,onDeactivated,watch} from 'vue'
import {getInterpretationFinancePage,saveInterpretationSettlementMode} from '@/api/interpretationCustomerFinance'
import InterpretationFinanceEditor from '@/components/common/InterpretationFinanceEditor.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import {useTableColumns} from '@/composables/useTableColumns'
import {translationSettlementModeLabels as settlementModeLabels} from '@/utils/settlementModes'
import {formatFinanceAmounts,interpretationUnitPrice,interpretationWorkload} from '@/utils/interpretationCustomerFinance'
import {ElMessage} from 'element-plus'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import FinanceManagerNameSelect from '@/components/common/FinanceManagerNameSelect.vue'
import CustomerQuotationDialog from '@/components/common/CustomerQuotationDialog.vue'
import InterpretationStatementDialog from '@/components/common/InterpretationStatementDialog.vue'
import InterpretationInvoiceDialog from '@/components/common/InterpretationInvoiceDialog.vue'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
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
  {key:'totals_excl_tax',label:'不含税总价',width:127},
  {key:'totals_incl_tax',label:'含税总价',width:127},
  {key:'settlement_mode',label:'结算模式',width:148},
  {key:'documents',label:'单据需求',width:121},
  {key:'payment_status',label:'收款状态',width:105},
  {key:'billing_totals',label:'计费合计',width:127},
  {key:'explanation',label:'说明',width:165},
  {key:'totals',label:'原总价（税口径未确认）',width:185},
  {key:'adjusted_totals',label:'调整后总价',width:145},
]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('interpretation-customer-finance',columns,
  ['order_no','project_name','client_short_name','project_status','directions','workload','pricing_mode','billing_month',
    'rates','totals_excl_tax','totals_incl_tax','settlement_mode','documents','payment_status'],{
    legacyDefaultKeys:['order_no','project_name','client_short_name','project_status','directions','pricing_mode','billing_month',
      'settlement_mode','rates','totals_excl_tax','totals_incl_tax','billing_totals'],
  })
const visibleColumns=computed(()=>columns.filter(col=>isVisible(col.key)))
const canWrite=hasPermission('projects:write'),selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const canReadProjects=hasPermission('projects:read')||canWrite
const quotationVisible=ref(false),statementVisible=ref(false),invoiceVisible=ref(false)
const actionRow=ref(null),financeEditor=ref(null),editorTarget=ref('')
const totalsExclTax=ref({}),totalsInclTax=ref({}),billingTotals=ref({})
const pricingModes={time:'按时长计费',fixed:'固定收费'}
const advancedVisible=ref(false),settlementSaving=reactive(new Set())
const defaultAdvanced=()=>({pricing:'',settlement:'',paymentStatus:'',missingAmount:false})
const filters=reactive({keyword:'',month:'',manager:props.clientScope?'all':'self',managerName:'',...defaultAdvanced()}),rows=ref([]),incomplete=ref(0),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
const advancedCount=computed(()=>[filters.pricing,filters.settlement,filters.paymentStatus,filters.missingAmount].filter(Boolean).length)
const documentProjects=computed(()=>actionRow.value?[actionRow.value]:rows.value)
function financeRowActions(row){
  const history={command:'history',label:'修改记录'}
  const mode=row.settlement_mode
  if(mode==='special')return [{command:'invoice',label:'特殊结算'},history]
  const labels={
    monthly:['合并对账单','合并结算发票'],
    sub_client:['子客户对账单','子客户结算发票'],
  }
  const [statement,invoice]=labels[mode]||['对账单','发票']
  return [
    {command:'price',label:canWrite?'价格与收费':'查看价格与收费'},
    {command:'quotation',label:'报价单'},
    {command:'statement',label:statement,disabled:!row.billing_month},
    {command:'invoice',label:invoice},
    history,
  ]
}
function openDocument(command,row=null){
  actionRow.value=row
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
let activated=false
function queryParams(){return {client_id:props.clientId||undefined,month:filters.month||undefined,pricing_mode:filters.pricing||undefined,payment_method:filters.settlement||undefined,payment_status:filters.paymentStatus||undefined,missing_amount:filters.missingAmount||undefined,only_mine:filters.manager==='self',client_manager:filters.manager==='name'?filters.managerName:undefined}}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getInterpretationFinancePage({...queryParams(),keyword:filters.keyword,skip:(page.value-1)*10,limit:10},controller.signal);if(seq===sequence){totalsExclTax.value=data.totals_excl_tax||{};totalsInclTax.value=data.totals_incl_tax||{};billingTotals.value=data.billing_totals||{};rows.value=data.items;total.value=data.total;incomplete.value=data.incomplete}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'口译财务加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function clearAdvanced(){Object.assign(filters,defaultAdvanced());search()}
function reset(){Object.assign(filters,defaultAdvanced());filters.keyword='';filters.month='';filters.manager=props.clientScope?'all':'self';filters.managerName='';search()}
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
const paymentStatus={unrecorded:'未登记',deposit:'已收定金',partial:'已收部分款',full:'已收全款'}
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
    return (row.payload?.rates||[]).map(rate=>`${rate.direction}\n${format(rate)}`).join('\n')||'待填写'
  }
  if(['totals','adjusted_totals','totals_excl_tax','totals_incl_tax','billing_totals'].includes(key))return formatFinanceAmounts(row[key])
  if(key==='explanation')return row.payload.explanation||'-'
  return row[key]||'-'
}
onMounted(()=>void load())
onActivated(()=>{if(activated)void load();activated=true})
watch(()=>props.clientId,search)
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
onDeactivated(()=>{quotationVisible.value=false;statementVisible.value=false;invoiceVisible.value=false;editorTarget.value=''})
useProjectStatusSync('interpretation',rows,{field:'project_status',onChanged:()=>{if(!loading.value)void load()}})
</script>
<style scoped>
.heading,.heading-actions{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}.heading-actions>.el-button{margin:0}.finance-rate{display:grid;gap:3px;line-height:1.45}.finance-rate+.finance-rate{margin-top:6px;padding-top:6px;border-top:1px solid var(--el-border-color-lighter)}.finance-rate strong{font-size:12px}.finance-advanced{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 12px}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}.finance-detail{max-height:560px;overflow-y:auto}.el-pagination{margin:16px 0}.el-select{width:100%}.finance-advanced :deep(.el-form-item){margin-right:0}p{font-size:12px;color:#64748b}
</style>
