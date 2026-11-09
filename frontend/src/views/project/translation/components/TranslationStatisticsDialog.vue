<template>
  <DraggableFormDialog :model-value="modelValue" title="笔译项目 · 数据统计" width="min(1500px, calc(100vw - 32px))" top="4vh" class="translation-statistics-dialog" destroy-on-close @update:model-value="$emit('update:modelValue',$event)">
    <AppForm inline class="statistics-query" @submit.prevent="load">
      <el-form-item label="统计日期"><el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" @change="query" /></el-form-item>
      <el-form-item label="统计周期"><el-radio-group v-model="granularity" @change="query"><el-radio-button value="day">每天</el-radio-button><el-radio-button value="week">每周</el-radio-button><el-radio-button value="month">每月</el-radio-button></el-radio-group></el-form-item>
      <el-form-item label="客户名称"><el-input v-model="keyword" clearable placeholder="客户全称、简称或编号" @input="search" @keyup.enter="query" /></el-form-item>
      <el-form-item><el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button><el-popover trigger="click" placement="bottom-end" :width="420"><template #reference><el-button>高级筛选{{ advancedCount?`（${advancedCount}）`:'' }}</el-button></template><div class="statistics-advanced"><label>日期依据</label><el-select v-model="dateBasis" aria-label="日期依据" @change="query"><el-option label="订单号中的日期" value="order" /><el-option label="客户接单时间" value="reception" /></el-select><label>金额口径</label><el-select v-model="taxBasis" aria-label="金额口径" @change="query"><el-option label="不含税金额" value="excl_tax" /><el-option label="含税金额" value="incl_tax" /></el-select><el-button @click="clearAdvanced">清空高级条件</el-button></div></el-popover></el-form-item>
    </AppForm>
    <div class="statistics-shortcuts"><el-button v-for="item in shortcuts" :key="item.key" size="small" @click="shortcut(item.key)">{{ item.label }}</el-button><span>按{{ dateBasis==='order'?'订单号日期':'客户接单时间' }} · {{ taxBasis==='excl_tax'?'不含税':'含税' }} · 周一至周日</span></div>
    <details class="statistics-definition"><summary>统计口径说明</summary><p>每个母订单计为一单，各级子订单金额逐级汇总，不重复计算。统计包含全部已保存项目状态，不包含尚未保存的窗口内容。</p><p>新客户：在该日／周／月首次产生笔译订单的客户；老客户：更早已有笔译订单的客户。客户数量按客户档案去重，未关联客户的订单单列；客户占比以本周期有订单的已关联客户数为分母，订单占比以本周期全部母订单数为分母。筛选客户后，占比在筛选结果内计算。跨期范围只统计所选日期，新老客户仍按完整自然周期判断。</p><p>金额沿用“价格与付款”的实际计算及调整结果，按币种分列；总金额是目前已登记金额之和。单均金额＝该币种金额完整的母订单总金额÷对应订单数；金额待补或部分待补的订单不参与单均计算。日期依据缺失时回退到创建日期，所有日期以 UTC+8 为准。</p></details>
    <el-alert v-if="failure" type="error" :closable="false" :title="failure" show-icon />
    <div v-loading="loading" class="statistics-results">
      <template v-if="data">
        <div class="statistics-report-meta">共 {{ data.order_count }} 个母订单 · {{ data.periods.length }} 个周期<span v-if="data.fallback_date_orders"> · {{ data.fallback_date_orders }} 单采用创建日期</span><span v-if="data.undated_orders"> · {{ data.undated_orders }} 个历史项目缺少可识别日期，未纳入统计</span><span> · 更新于 {{ formatBusinessDateTimeMinute(data.generated_at) }}</span></div>
        <el-tabs v-model="tab">
          <el-tab-pane label="周期概览" name="overview">
            <el-table :data="data.periods" border max-height="470" empty-text="所选日期没有订单" class="statistics-overview">
              <el-table-column label="周期" min-width="200" fixed><template #default="{row}">{{ period(row) }}</template></el-table-column>
              <el-table-column prop="order_count" label="订单数" width="85" />
              <el-table-column prop="customer_count" label="客户数" width="85" />
              <el-table-column label="新客户数 / 占比" min-width="145"><template #default="{row}">{{ row.new_customer_count }} / {{ percent(row.new_customer_share) }}</template></el-table-column>
              <el-table-column label="老客户数 / 占比" min-width="145"><template #default="{row}">{{ row.old_customer_count }} / {{ percent(row.old_customer_share) }}</template></el-table-column>
              <el-table-column label="新客户订单 / 占比" min-width="165"><template #default="{row}">{{ row.new_order_count }} / {{ percent(row.new_order_share) }}</template></el-table-column>
              <el-table-column label="老客户订单 / 占比" min-width="165"><template #default="{row}">{{ row.old_order_count }} / {{ percent(row.old_order_share) }}</template></el-table-column>
              <el-table-column label="未关联客户订单" min-width="145"><template #default="{row}">{{ row.unknown_order_count }} / {{ percent(row.unknown_order_share) }}</template></el-table-column>
              <el-table-column label="总金额（按币种）" min-width="190"><template #default="{row}"><div v-for="item in row.amounts" :key="item.currency">{{ item.currency }} {{ money(item.total_amount) }}</div><span v-if="!row.amounts.length">—</span></template></el-table-column>
              <el-table-column label="单均金额（完整计价订单）" min-width="220"><template #default="{row}"><div v-for="item in row.amounts" :key="item.currency">{{ item.currency }} {{ money(item.average_amount) }} <small>（{{ item.complete_order_count }} 单）</small></div><span v-if="!row.amounts.length">—</span></template></el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane :label="`客户明细（${data.customers.length}）`" name="customers">
            <el-table :data="customerPage" border max-height="430" empty-text="所选日期没有客户订单" class="statistics-customers">
              <el-table-column label="周期" min-width="200" fixed><template #default="{row}">{{ period(row) }}</template></el-table-column>
              <el-table-column prop="client_short_name" label="客户简称" min-width="160" show-overflow-tooltip /><el-table-column prop="client_name" label="客户全称" min-width="200" show-overflow-tooltip />
              <el-table-column label="新老客户" width="110"><template #default="{row}"><el-tag :type="row.cohort==='new'?'success':'info'">{{ {new:'新客户',old:'老客户',unknown:'未关联客户'}[row.cohort] }}</el-tag></template></el-table-column>
              <el-table-column prop="first_order_date" label="首次笔译下单" width="135" />
              <el-table-column prop="order_count" label="订单数" width="85" /><el-table-column label="订单占比" width="100"><template #default="{row}">{{ percent(row.order_share) }}</template></el-table-column>
              <el-table-column label="总金额（按币种）" min-width="190"><template #default="{row}"><div v-for="item in row.amounts" :key="item.currency">{{ item.currency }} {{ money(item.total_amount) }}</div><span v-if="!row.amounts.length">—</span></template></el-table-column>
              <el-table-column label="单均金额（完整计价订单）" min-width="220"><template #default="{row}"><div v-for="item in row.amounts" :key="item.currency">{{ item.currency }} {{ money(item.average_amount) }} <small>（{{ item.complete_order_count }} 单）</small></div><span v-if="!row.amounts.length">—</span></template></el-table-column>
              <el-table-column prop="missing_amount_orders" label="金额未登记订单" width="145" /><el-table-column prop="partial_amount_orders" label="金额部分待补订单" width="155" />
            </el-table>
            <el-pagination v-model:current-page="page" :page-size="20" :total="data.customers.length" layout="total, prev, pager, next" />
          </el-tab-pane>
        </el-tabs>
      </template><el-empty v-else-if="!loading && !failure" description="请选择日期进行统计" />
    </div>
    <template #footer><el-button @click="$emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {getTranslationStatistics} from '@/api/translationStatistics'
import {businessDateTimeInputValue,formatBusinessDateTimeMinute} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Boolean});defineEmits(['update:modelValue'])
const today=()=>businessDateTimeInputValue().slice(0,10)
const defaultRange=()=>[today().slice(0,7)+'-01',today()]
const range=ref(defaultRange()),granularity=ref('month'),keyword=ref(''),dateBasis=ref('order'),taxBasis=ref('excl_tax'),tab=ref('overview'),page=ref(1),loading=ref(false),failure=ref(''),data=ref(null)
const advancedCount=computed(()=>Number(dateBasis.value!=='order')+Number(taxBasis.value!=='excl_tax'))
const customerPage=computed(()=>data.value?.customers.slice((page.value-1)*20,page.value*20)||[])
const shortcuts=[{key:'week',label:'本周'},{key:'lastWeek',label:'上周'},{key:'month',label:'本月'},{key:'lastMonth',label:'上月'}]
const percent=value=>Number(value||0).toFixed(2)+'%'
const money=value=>value===null||value===undefined?'—':Number(value).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const period=row=>row.period_start===row.period_end?row.period_start:row.period_start+' 至 '+row.period_end
let timer=null,controller=null,sequence=0
function query(){clearTimeout(timer);page.value=1;void load()}
function search(value){clearTimeout(timer);if(!value)return query();timer=setTimeout(query,400)}
async function load(){
 if(!props.modelValue)return
 controller?.abort();const current=++sequence;controller=new AbortController();failure.value='';data.value=null
 if(!range.value?.[0]||!range.value?.[1]||range.value[0]>range.value[1]){loading.value=false;failure.value='请选择有效的开始及结束日期';return}
 const owner=localStorage.getItem('user_id');loading.value=true
 try{const result=await getTranslationStatistics({start:range.value[0],end:range.value[1],granularity:granularity.value,date_basis:dateBasis.value,tax_basis:taxBasis.value,client_keyword:keyword.value.trim()},{signal:controller.signal});if(current===sequence&&props.modelValue&&owner===localStorage.getItem('user_id'))data.value=result}
 catch(error){if(current===sequence&&error?.code!=='ERR_CANCELED'&&error?.name!=='CanceledError'&&error?.name!=='AbortError')failure.value=getLocalizedErrorMessage(error,'统计读取失败，请重试')}
 finally{if(current===sequence)loading.value=false}
}
function clearAdvanced(){dateBasis.value='order';taxBasis.value='excl_tax';query()}
function reset(){range.value=defaultRange();keyword.value='';dateBasis.value='order';taxBasis.value='excl_tax';granularity.value='month';query()}
function shortcut(key){
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
watch(()=>props.modelValue,visible=>{if(visible){data.value=null;failure.value='';page.value=1;query()}else{cancel();data.value=null}},{immediate:true})
onBeforeUnmount(cancel)
</script>
<style>
.translation-statistics-dialog{display:flex;flex-direction:column;max-height:92vh;overflow:hidden}.translation-statistics-dialog>.el-dialog__body{min-height:0;overflow:auto}.translation-statistics-dialog>.el-dialog__header,.translation-statistics-dialog>.el-dialog__footer{flex:none}.statistics-query{display:flex;flex-wrap:wrap;gap:8px}.statistics-query .el-form-item{margin-right:0;margin-bottom:8px}.statistics-shortcuts{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0 12px}.statistics-shortcuts span,.statistics-report-meta{font-size:12px;color:var(--el-text-color-secondary)}.statistics-definition{font-size:12px;line-height:1.7;margin-bottom:12px;color:var(--el-text-color-regular)}.statistics-definition summary{cursor:pointer}.statistics-definition p{margin:5px 0}.statistics-results{min-height:160px}.statistics-advanced{display:grid;gap:10px;max-height:min(560px,calc(100vh - 120px));overflow:auto}.translation-statistics-dialog .el-pagination{margin-top:10px}.translation-statistics-dialog small{color:var(--el-text-color-secondary)}@media(max-width:700px){.statistics-query .el-form-item{width:100%}.statistics-query .el-date-editor{max-width:100%}}
</style>
