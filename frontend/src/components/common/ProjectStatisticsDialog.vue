<template>
  <DraggableFormDialog :model-value="modelValue" :title="`${moduleLabel}项目 · 数据统计`" width="min(1500px, calc(100vw - 32px))" top="4vh" class="translation-statistics-dialog" destroy-on-close @update:model-value="$emit('update:modelValue',$event)">
    <section class="statistics-filter-group"><AppForm inline class="statistics-query" data-auto-draft="off"><el-form-item label="统计日期"><el-date-picker v-model="range" :disabled="allDates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" @change="query" /></el-form-item><el-form-item label="日期范围"><el-switch v-model="allDates" aria-label="全部日期" active-text="全部日期" @change="query"/></el-form-item></AppForm><div class="statistics-shortcuts"><el-button v-for="item in shortcuts" :key="item.key" size="small" @click="shortcut(item.key)">{{item.label}}</el-button><span>按{{dateBasis==='order'?'订单号日期':receptionLabel}} · 周一至周日</span></div></section>
    <div class="statistics-secondary-filters"><section class="statistics-period-filter"><AppForm inline class="statistics-query" data-auto-draft="off"><el-form-item label="统计周期"><el-radio-group v-model="granularity" @change="query"><el-radio-button value="day">每天</el-radio-button><el-radio-button value="week">每周</el-radio-button><el-radio-button value="month">每月</el-radio-button><el-radio-button v-if="hasStatusStatistics" value="quarter">每季度</el-radio-button><el-radio-button v-if="hasStatusStatistics" value="all">全部汇总</el-radio-button></el-radio-group></el-form-item></AppForm></section><section class="statistics-customer-filter"><AppForm inline class="statistics-query" data-auto-draft="off" @submit.prevent="query"><el-form-item label="客户名称"><el-input v-model="keyword" clearable placeholder="客户全称、简称或编号" @input="search" @keyup.enter="query" /></el-form-item><el-form-item><el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button><el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="420" :popper-style="{maxWidth:'calc(100vw - 32px)'}"><template #reference><el-button>高级筛选{{ advancedCount?`（${advancedCount}）`:'' }}</el-button></template><div class="statistics-advanced" data-auto-draft="off"><label>日期依据</label><el-select v-model="dateBasis" aria-label="日期依据" @change="query"><el-option label="订单号中的日期" value="order" /><el-option :label="receptionLabel" value="reception" /></el-select><template v-if="showMoney"><label>金额口径</label><el-select v-model="taxBasis" aria-label="金额口径" @change="query"><el-option label="不含税金额" value="excl_tax" /><el-option label="含税金额" value="incl_tax" /></el-select></template><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advancedVisible=false">关闭</el-button></div></el-popover></el-form-item></AppForm></section></div>
    <details class="statistics-definition"><summary>统计口径说明</summary><p>每个母订单计为一单，不重复计算下级订单。统计包含全部已保存项目状态，不包含尚未保存的窗口内容。</p><p>新老客户按笔译、口译、标注、招聘的母订单合并判断。限定日期时，首次订单落在范围内且范围内只有1单的临时呈现为新客户；范围内至少2单或首次订单早于范围的为老客户。全部日期按日常规则及手动设置显示。客户数量按客户档案去重，未关联客户的订单单列；客户占比以本周期有订单的已关联客户数为分母，订单占比以本周期全部母订单数为分母。筛选客户后，占比在筛选结果内计算。跨期范围只统计所选日期，新老客户仍按完整自然周期判断。</p><p v-if="showMoney">金额沿用“价格与付款”的实际计算及调整结果，按币种分列；总金额是目前已登记金额之和。单均金额＝该币种金额完整的母订单总金额÷对应订单数；金额待补或部分待补的订单不参与单均计算。日期依据缺失时回退到创建日期，所有日期以 UTC+8 为准。</p><p v-if="hasStatusStatistics">项目状态以当前已保存的状态为准，并非过去某时点的状态快照。状态占比＝该状态的母订单数÷本周期全部母订单数；空白及其他历史状态也计入分母。季度按自然季度、周按周一至周日；全部汇总将所选日期合为一个周期，“全部日期”则取消日期范围限制。合并只合计已成交待执行、进行中、已结束、已结款，不重复计算这四项。</p><p v-if="!showMoney">本窗口统计客户、订单及金额；客户咨询时间缺失时回退到创建日期，日期统一使用 UTC+8。</p></details>
    <el-alert v-if="failure" type="error" :closable="false" :title="failure" show-icon />
    <div v-loading="loading" class="statistics-results">
      <template v-if="data">
        <div class="statistics-amount-currency"><label>金额排序币种</label><el-select v-model="tableCurrency" aria-label="金额排序币种" style="width:130px"><el-option v-for="code in tableCurrencies" :key="code" :value="code" :label="code"/></el-select><small>金额不跨币种相加；单均只计算金额完整的母订单。</small></div><div class="statistics-report-meta">共 {{ data.order_count }} 个母订单 · {{ data.periods.length }} 个周期<span v-if="data.fallback_date_orders"> · {{ data.fallback_date_orders }} 单采用创建日期</span><span v-if="data.undated_orders"> · {{ data.undated_orders }} 个历史项目缺少可识别日期，未纳入统计</span><span> · 更新于 {{ formatBusinessDateTimeMinute(data.generated_at) }}</span></div>
        <el-tabs v-model="tab">
          <el-tab-pane v-if="hasStatusStatistics" label="项目状态" name="statuses">
            <div v-if="canMergeDealStatuses" class="statistics-status-options"><el-switch v-model="mergeDealStatuses" aria-label="合并已成交的四个状态" active-text="合并已成交的四个状态" @change="query" /><span>已成交待执行、进行中、已结束、已结款</span></div>
            <div class="statistics-chart-scope"><label>饼图范围</label><el-select v-model="chartPeriod" aria-label="饼图范围" style="width:300px;max-width:100%"><el-option label="全部查询结果" value="all"/><el-option v-for="row in data.periods" :key="row.period_start" :value="row.period_start" :label="period(row)"/></el-select></div>
            <ProjectStatusPie :columns="data.status_columns||[]" :counts="chartCounts" :deals="chartDeals" @select="openStatusCustomers"/>
            <StatisticsTable :rows="data.periods" :columns="statusColumns" class="statistics-statuses" @filtered="filteredStatusPeriods=$event"><template #cell="{row,column,value}"><el-popover v-if="column.statusKey==='deal_merged'" trigger="click" placement="left" :width="360"><template #reference><el-button link type="primary">{{value}} · 查看详情</el-button></template><strong>四个已成交状态 · {{period(row)}}</strong><el-table :data="Object.values(row.deal_status_counts||{})" size="small"><el-table-column prop="label" label="状态"/><el-table-column prop="count" label="数量" width="65"/><el-table-column label="占本周期"><template #default="{row:detail}">{{percent(detail.share)}}</template></el-table-column></el-table></el-popover><StatisticsOrderDetails v-else-if="column.key==='order_count'" :orders="row.orders||[]" :label="value"/><span v-else>{{value}}</span></template></StatisticsTable>
          </el-tab-pane>
          <el-tab-pane label="周期概览" name="overview">
            <StatisticsTable :rows="data.periods" :columns="overviewColumns" class="statistics-overview" @filtered="filteredOverviewPeriods=$event"><template #cell="{row,column,value}"><StatisticsOrderDetails v-if="['order_count','amounts'].includes(column.key)" :orders="row.orders||[]" :label="value"/><span v-else>{{value}}</span></template></StatisticsTable>
            <StatisticsCustomerCharts :rows="overviewCustomers"/>
          </el-tab-pane>
          <el-tab-pane :label="`客户明细（${data.customers.length}）`" name="customers">
            <StatisticsTable :rows="data.customers" :columns="customerColumns" class="statistics-customers" @filtered="filteredCustomers=$event"><template #cell="{row,column,value}"><StatisticsOrderDetails v-if="['order_count','amounts'].includes(column.key)" :orders="row.orders||[]" :label="value"/><el-tag v-else-if="column.key==='cohort'" :type="row.cohort==='new'?'success':'info'">{{value}}</el-tag><span v-else>{{value}}</span></template></StatisticsTable>
            <StatisticsCustomerCharts :rows="filteredCustomers"/>
          </el-tab-pane>
          <el-tab-pane v-if="showReasons" :label="`查看未成交原因（${data.unconverted_projects?.length||0}）`" name="unconverted">
            <p class="statistics-reason-hint">列出{{module==='recruitment'?'已取消':'已取消、已部分取消'}}的项目；原因取状态变更时填写的“进度/说明”，未登记的显示“未填写”。</p>
            <StatisticsTable :rows="data.unconverted_projects||[]" :columns="reasonColumns" @filtered="filteredReasons=$event"><template #cell="{row,column,value}"><el-button v-if="column.key==='classification_paths'&&module==='interpretation'&&row.classification_id&&canReview" link type="primary" @click="reviewReason(row)">{{value}} · 调整原因</el-button><ScreenshotText v-else-if="column.key==='reason'" :text="value"/><span v-else>{{value}}</span></template></StatisticsTable><CancellationReasonCharts :rows="filteredReasons"/>
          </el-tab-pane>
        </el-tabs>
      </template><el-empty v-else-if="!loading && !failure" description="请选择日期进行统计" />
    </div>
    <StatisticsCustomersDialog ref="statusCustomers"/><PartialCancellationReasonDialog ref="reasonEditor"/>
    <template #footer><el-button @click="$emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import StatisticsTable from './StatisticsTable.vue'
import StatisticsOrderDetails from './StatisticsOrderDetails.vue'
import StatisticsCustomerCharts from './StatisticsCustomerCharts.vue'
import ProjectStatusPie from './ProjectStatusPie.vue'
import ScreenshotText from './ScreenshotText.vue'
import StatisticsCustomersDialog from './StatisticsCustomersDialog.vue'
import CancellationReasonCharts from './CancellationReasonCharts.vue'
import PartialCancellationReasonDialog from './PartialCancellationReasonDialog.vue'
import api from '@/api'
import {ElMessage} from 'element-plus'
import {hasPermission} from '@/utils/permission'
import {getProjectStatistics} from '@/api/projectStatistics'
import {businessDateTimeInputValue,formatBusinessDateTimeMinute} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Boolean,module:{type:String,default:'translation'}});
const moduleLabel=computed(()=>({translation:'笔译',interpretation:'口译',annotation:'标注',recruitment:'招聘'}[props.module]||'项目'))
const showMoney=computed(()=>true)
const hasStatusStatistics=computed(()=>true)
const canMergeDealStatuses=computed(()=>props.module==='interpretation')
const showReasons=computed(()=>['interpretation','recruitment'].includes(props.module))
const allDates=ref(false),mergeDealStatuses=ref(true)
const receptionLabel=computed(()=>props.module==='translation'?'客户接单时间':'客户咨询时间')
defineEmits(['update:modelValue'])
const today=()=>businessDateTimeInputValue().slice(0,10)
const defaultRange=()=>[today().slice(0,7)+'-01',today()]
const advancedVisible=ref(false)
const range=ref(defaultRange()),granularity=ref('month'),keyword=ref(''),dateBasis=ref('order'),taxBasis=ref('excl_tax'),tab=ref('overview'),page=ref(1),loading=ref(false),failure=ref(''),data=ref(null)
const advancedCount=computed(()=>Number(dateBasis.value!=='order')+Number(taxBasis.value!=='excl_tax'))
const customerPage=computed(()=>data.value?.customers.slice((page.value-1)*20,page.value*20)||[])
const chartPeriod=ref('all'),reasonPage=ref(1)
const chartRow=computed(()=>chartPeriod.value==='all'?null:data.value?.periods.find(row=>row.period_start===chartPeriod.value))
const filteredStatusPeriods=ref(null),filteredOverviewPeriods=ref(null)
const aggregate=(rows,key)=>{const result={};for(const row of rows)for(const [name,item] of Object.entries(row[key]||{})){result[name]??={...item,count:0};result[name].count+=Number(item.count||0)}return result}
const chartRows=computed(()=>chartPeriod.value==='all'?(filteredStatusPeriods.value??data.value?.periods??[]):(filteredStatusPeriods.value??data.value?.periods??[]).filter(row=>row.period_start===chartPeriod.value))
const chartCounts=computed(()=>aggregate(chartRows.value,'status_counts'))
const overviewCustomers=computed(()=>(data.value?.customers||[]).filter(row=>(filteredOverviewPeriods.value??data.value?.periods??[]).some(period=>period.period_start===row.period_start)))
const chartDeals=computed(()=>aggregate(chartRows.value,'deal_status_counts'))
const unconvertedPage=computed(()=>(data.value?.unconverted_projects||[]).slice((reasonPage.value-1)*20,reasonPage.value*20))
const shortcuts=[{key:'week',label:'本周'},{key:'lastWeek',label:'上周'},{key:'month',label:'本月'},{key:'lastMonth',label:'上月'}]
const percent=value=>Number(value||0).toFixed(2)+'%'
const money=value=>value===null||value===undefined?'—':Number(value).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const period=row=>data.value?.granularity==='all'?'合计（'+row.period_start+' 至 '+row.period_end+'）':row.period_start===row.period_end?row.period_start:row.period_start+' 至 '+row.period_end
const statusCustomers=ref(),reasonEditor=ref(),filteredReasons=ref([])
const canReview=hasPermission('projects:write')
function openStatusCustomers(slice){const rows=chartRows.value.flatMap(row=>row.orders||[]).filter(order=>slice.key==='deal_merged'?['deal_pending_execution','in_progress','ended','settled'].includes(order.status):order.status===slice.key);statusCustomers.value.open(slice.label,rows)}
async function reviewReason(row){try{const project=await api.get('/projects/interpretation/'+row.id);const interpreters=(project.interpreter_assignments||project.interpreterAssignments||[]).map(person=>({...person,translatorLabel:person.translator_name||person.translatorName}));const result=await reasonEditor.value.open(row.original_reason||row.reason||'',{status:row.status,details:row.classification_details,interpreters});if(result==null)return;await api.put('/projects/interpretation/'+row.id+'/cancellation-classification',{classification_id:row.classification_id,expected_details:row.classification_details,details:reasonEditor.value.getDetails()});ElMessage.success('原因分类已更新，原始说明已保留');await query()}catch(error){ElMessage.error(error.detail||error.message||'调整原因失败')}}
const filteredCustomers=ref([]),tableCurrency=ref('CNY')
const tableCurrencies=computed(()=>[...new Set(['CNY',...(data.value?.customers||[]).flatMap(row=>(row.amounts||[]).map(item=>item.currency))])].sort())
const amountText=(row,field='total_amount')=>(row.amounts||[]).map(item=>item.currency+' '+money(item[field])).join('；')||'未登记'
const amountSort=(row,field='total_amount')=>Number((row.amounts||[]).find(item=>item.currency===tableCurrency.value)?.[field]??-1)
const periodColumn={key:'period_start',label:'周期',width:200,format:period}
const countColumn={key:'order_count',label:'订单数',width:100}
const amountColumns=[{key:'amounts',label:'项目金额（按币种）',width:200,format:row=>amountText(row),sort:row=>amountSort(row)},{key:'average_amount',label:'单均金额（完整计价订单）',width:220,format:row=>amountText(row,'average_amount'),sort:row=>amountSort(row,'average_amount')}]
const statusColumns=computed(()=>[periodColumn,{...countColumn,label:'项目总数'},...(data.value?.status_columns||[]).map(column=>({key:'status_'+column.key,statusKey:column.key,label:column.label+' · 数量 / 占比',width:190,format:row=>(row.status_counts?.[column.key]?.count||0)+' / '+percent(row.status_counts?.[column.key]?.share),sort:row=>row.status_counts?.[column.key]?.count||0}))])
const shareColumn=(key,label)=>({key,label,width:155,format:row=>row[key.replace('_share','_count')]+' / '+percent(row[key]),sort:row=>Number(row[key]||0)})
const overviewColumns=computed(()=>[periodColumn,countColumn,{key:'customer_count',label:'客户数'},shareColumn('new_customer_share','新客户数 / 占比'),shareColumn('old_customer_share','老客户数 / 占比'),shareColumn('new_order_share','新客户订单 / 占比'),shareColumn('old_order_share','老客户订单 / 占比'),shareColumn('unknown_order_share','未关联客户订单 / 占比'),...amountColumns])
const customerColumns=computed(()=>[periodColumn,{key:'client_short_name',label:'客户简称',width:170},{key:'client_name',label:'客户全称',width:210},{key:'cohort',label:'新老客户',format:row=>({new:'新客户',old:'老客户',unknown:'未关联客户'}[row.cohort]||'未关联客户')},{key:'first_order_date',label:'首次下单日期',width:140},countColumn,{key:'order_share',label:'订单占比',format:row=>percent(row.order_share),sort:row=>Number(row.order_share||0)},...amountColumns,{key:'missing_amount_orders',label:'金额未登记订单'},{key:'partial_amount_orders',label:'金额部分待补订单'}])
const reasonColumns=[{key:'order_no',label:'订单号',width:150},{key:'project_name',label:'项目名称',width:210},{key:'client_short_name',label:'客户简称'},{key:'status_label',label:'项目状态'},{key:'classification_paths',label:'取消原因分类',width:240,format:row=>(row.classification_paths||[]).map(path=>path.join(' / ')).join('；')+(row.classification_needs_review?'（待复核）':'')||'未分类'},{key:'reason',label:'未成交原因／状态说明',width:320,format:row=>props.module==='interpretation'&&row.reason==='项目取消'?'客户未回复原因':row.reason||'未填写'},{key:'reason_at',label:'说明登记时间',width:170,format:row=>row.reason_at?formatBusinessDateTimeMinute(row.reason_at):'未填写'}]
let timer=null,controller=null,sequence=0
function query(){clearTimeout(timer);page.value=1;reasonPage.value=1;chartPeriod.value='all';void load()}
function search(value){clearTimeout(timer);if(!value)return query();timer=setTimeout(query,400)}
async function load(){
 if(!props.modelValue)return
 controller?.abort();const current=++sequence;controller=new AbortController();failure.value=''
 if(!allDates.value&&(!range.value?.[0]||!range.value?.[1]||range.value[0]>range.value[1])){loading.value=false;failure.value='请选择有效的开始及结束日期';return}
 const owner=localStorage.getItem('user_id');loading.value=true
 try{const result=await getProjectStatistics(props.module,{start:range.value[0],end:range.value[1],granularity:granularity.value,date_basis:dateBasis.value,tax_basis:taxBasis.value,client_keyword:keyword.value.trim(),...(hasStatusStatistics.value?{all_dates:allDates.value,merge_deal_statuses:canMergeDealStatuses.value&&mergeDealStatuses.value}:{})},{signal:controller.signal});if(current===sequence&&props.modelValue&&owner===localStorage.getItem('user_id'))data.value=result}
 catch(error){if(current===sequence&&error?.code!=='ERR_CANCELED'&&error?.name!=='CanceledError'&&error?.name!=='AbortError'){data.value=null;failure.value=getLocalizedErrorMessage(error,'统计读取失败，请重试')}}
 finally{if(current===sequence)loading.value=false}
}
function clearAdvanced(){dateBasis.value='order';taxBasis.value='excl_tax';query()}
function restoreFilterDefaults(){range.value=defaultRange();keyword.value='';dateBasis.value='order';taxBasis.value='excl_tax';granularity.value='month';allDates.value=false;mergeDealStatuses.value=true}
function reset(){restoreFilterDefaults();query()}

function shortcut(key){
 allDates.value=false
 const now=new Date(today()+'T00:00:00+08:00');const day=new Date(now.getTime()+8*3600000)
 let left,right
 if(key==='week'||key==='lastWeek'){
  const delta=(day.getUTCDay()+6)%7+(key==='lastWeek'?7:0);left=new Date(now.getTime()-delta*86400000);right=new Date(left.getTime()+6*86400000);granularity.value='week'
 }else{
  const month=day.getUTCMonth()-(key==='lastMonth'?1:0);left=new Date(Date.UTC(day.getUTCFullYear(),month,1)-8*3600000);right=new Date(Date.UTC(day.getUTCFullYear(),month+1,1)-8*3600000-86400000);granularity.value='month'
 }
 range.value=[businessDateTimeInputValue(left).slice(0,10),businessDateTimeInputValue(right).slice(0,10)];query()
}
function cancel(){clearTimeout(timer);controller?.abort();sequence++;loading.value=false}
watch(()=>[props.modelValue,props.module],([visible])=>{if(visible){data.value=null;failure.value='';page.value=1;tab.value=hasStatusStatistics.value?'statuses':'overview';query()}else{cancel();data.value=null;advancedVisible.value=false;restoreFilterDefaults()}},{immediate:true})
onBeforeUnmount(cancel)
</script>
<style>
.translation-statistics-dialog{display:flex;flex-direction:column;max-height:92vh;overflow:hidden}.translation-statistics-dialog>.el-dialog__body{min-height:0;overflow:auto}.translation-statistics-dialog>.el-dialog__header,.translation-statistics-dialog>.el-dialog__footer{flex:none}.statistics-query{display:flex;flex-wrap:wrap;gap:8px}.statistics-query .el-form-item{margin-right:0;margin-bottom:8px}.statistics-shortcuts{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0 12px}.statistics-shortcuts span,.statistics-report-meta{font-size:12px;color:var(--el-text-color-secondary)}.statistics-definition{font-size:12px;line-height:1.7;margin-bottom:12px;color:var(--el-text-color-regular)}.statistics-definition summary{cursor:pointer}.statistics-definition p{margin:5px 0}.statistics-results{min-height:160px}.statistics-advanced{display:grid;gap:10px;max-height:min(560px,calc(100vh - 120px));overflow:auto}.translation-statistics-dialog .el-pagination{margin-top:10px}.translation-statistics-dialog small{color:var(--el-text-color-secondary)}@media(max-width:700px){.statistics-query .el-form-item{width:100%}.statistics-query .el-date-editor{max-width:100%}}
</style>

<style scoped>
.statistics-secondary-filters{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--el-border-color-light);padding:8px 0}.statistics-customer-filter{margin-left:auto}.statistics-secondary-filters .statistics-query{margin:0}@media(max-width:900px){.statistics-customer-filter{margin-left:0;width:100%}}.statistics-amount-currency{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0;font-size:13px}.statistics-filter-group{border-bottom:1px solid var(--el-border-color-light);padding:8px 0}.statistics-chart-scope{display:flex;align-items:center;gap:12px;margin-bottom:10px}.statistics-reason-hint{font-size:13px;color:var(--el-text-color-secondary)}
.statistics-status-options{display:flex;align-items:center;flex-wrap:wrap;gap:8px 16px;margin-bottom:12px}
.statistics-status-options span{font-size:12px;color:var(--el-text-color-secondary)}
@media(max-width:700px){.statistics-query .el-radio-group{flex-wrap:wrap;gap:4px}}
</style>
