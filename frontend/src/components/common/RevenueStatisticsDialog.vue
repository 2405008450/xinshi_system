<template>
  <DraggableFormDialog :model-value="modelValue" class="revenue-statistics-dialog" width="min(1320px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" @update:model-value="$emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="营收统计" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
      <AppForm :model="filters" inline class="revenue-query" @submit.prevent="search">
        <el-form-item label="统计周期"><el-select v-model="filters.period" style="width:100px" @change="search"><el-option v-for="item in revenuePeriods" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item>
        <el-form-item label="所属日期"><el-date-picker v-model="filters.anchor" type="date" value-format="YYYY-MM-DD" :clearable="false" style="width:150px" @change="search" /></el-form-item>
        <el-form-item label="币种"><el-select v-model="filters.currency" style="width:100px" @change="search"><el-option v-for="currency in currencies" :key="currency" :value="currency" :label="currency" /></el-select></el-form-item>
        <el-form-item><el-button :loading="loading" @click="search">查询</el-button><el-button @click="reset">重置</el-button><AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearRanges" @reset="clearRanges">
          <AppForm :model="filters" label-position="top" @submit.prevent="search">
            <div class="revenue-range-grid"><el-form-item label="排名区间"><div class="revenue-range"><el-input-number v-model="filters.rankMin" :min="1" :precision="0" :controls="false" placeholder="起始名次" aria-label="起始名次" @change="search" /><span>至</span><el-input-number v-model="filters.rankMax" :min="1" :precision="0" :controls="false" placeholder="结束名次" aria-label="结束名次" @change="search" /></div></el-form-item>
            <el-form-item :label="`金额范围（${filters.currency}）`"><div class="revenue-range"><el-input-number v-model="filters.amountMin" :precision="2" :controls="false" placeholder="最低金额" aria-label="最低金额" @change="search" /><span>至</span><el-input-number v-model="filters.amountMax" :precision="2" :controls="false" placeholder="最高金额" aria-label="最高金额" @change="search" /></div></el-form-item></div>
            <p class="revenue-help">区间包含两端；起止值倒序时自动按大小归一。排名、金额条件同时生效。</p>
          </AppForm>
        </AdvancedFilterPopover></el-form-item>
      </AppForm>
      <p class="revenue-help">范围：{{scopeLabel}}。按订单日期归属；无法识别订单日期时采用客户交稿时间。周为周一至周日；按完整自然周期比较，当前周期可能尚未结束。币种分别统计。统计口径按客户选择后相加；选择仅影响本窗口并按当前用户记忆。</p>
      <div class="revenue-shortcuts"><span>排名快捷：</span><el-button v-for="item in rankShortcuts" :key="item.label" size="small" @click="chooseRank(item)">{{item.label}}</el-button><el-button size="small" @click="clearRank">不限排名</el-button><span>金额快捷：</span><el-button v-for="item in amountShortcuts" :key="item.label" size="small" @click="chooseAmount(item)">{{item.label}}</el-button><el-button size="small" @click="clearAmount">不限金额</el-button></div>
      <p v-if="rangeLabel" class="revenue-help">已选：{{rangeLabel}} <el-button link @click="clearRanges">清空区间条件</el-button></p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <div v-loading="loading">
        <template v-if="data">
          <h4 class="revenue-period">{{data.period.label}} · {{data.period.start}} 至 {{data.period.end}} <el-tag v-if="data.partial_period" type="warning" size="small">周期未结束</el-tag></h4>
          <div class="revenue-cards"><div><small>总营收 · {{data.currency}}</small><strong>{{revenueAmount(data.overall.amount)}}</strong><span>{{data.overall.customers}} 个有计费金额客户</span></div><div><small>同比 · {{data.last_year?.label||'无可比周期'}}</small><strong>{{revenueChange(data.overall.yoy)}}</strong><span>基期 {{revenueAmount(data.overall.yoy.amount)}} · 增减 {{revenueAmount(data.overall.yoy.difference)}}</span></div><div><small>环比 · {{data.previous.label}}</small><strong>{{revenueChange(data.overall.mom)}}</strong><span>基期 {{revenueAmount(data.overall.mom.amount)}} · 增减 {{revenueAmount(data.overall.mom.difference)}}</span></div></div>
          <el-alert v-if="data.overall.missing||data.missing_date||data.fallback_date" type="warning" :closable="false" :title="`本期 ${data.overall.missing} 个项目金额待补；范围内 ${data.fallback_date} 个项目采用客户交稿日期，另有 ${data.missing_date} 个项目无可用日期而未计入。金额待补时统计可能不完整。`" />
          <el-tabs v-model="activeTab">
            <el-tab-pane label="客户营收排名" name="ranking">
              <div class="revenue-ranking-toolbar"><el-input v-model="filters.keyword" clearable placeholder="客户全称或简称，多关键词搜索" style="width:290px;max-width:100%" @input="queueSearch" @keyup.enter="search" /><span>匹配 {{data.total}} / {{data.ranked_customers}} 个客户 · 筛选后合计 {{data.currency}} {{revenueAmount(data.filtered_amount)}}</span></div>
              <p class="revenue-help">排名按本期金额降序，同额按客户名称及编号排列；区间筛选后保留原排名。上期或去年同期有记录的客户本期无营收时仍列出。上方总营收和趋势不受排名、金额、客户关键词筛选影响。</p>
              <el-table :data="data.items" border row-key="key" empty-text="暂无匹配客户" max-height="440">
                <el-table-column prop="rank" label="排名" width="70" /><el-table-column prop="client_name" label="客户名称" min-width="170" show-overflow-tooltip /><el-table-column label="统计口径" width="170"><template #default="{row}"><el-select :model-value="row.basis" :disabled="!row.client_id" @change="value=>setBasis(row.client_id,value)"><el-option v-for="item in revenueBases" :key="item.value" :label="item.label" :value="item.value" /></el-select></template></el-table-column>
                <el-table-column label="本期营收" min-width="125" align="right"><template #default="{row}">{{revenueAmount(row.amount)}}<el-tag v-if="row.missing" size="small" type="warning">待补</el-tag></template></el-table-column>
                <el-table-column prop="projects" label="计费项目数" width="100" />
                <el-table-column label="同比" min-width="125"><template #default="{row}"><el-tooltip :content="`去年同期：${revenueAmount(row.yoy.amount)}；增减：${revenueAmount(row.yoy.difference)}`"><span>{{revenueChange(row.yoy)}}</span></el-tooltip></template></el-table-column>
                <el-table-column label="环比" min-width="125"><template #default="{row}"><el-tooltip :content="`上期：${revenueAmount(row.mom.amount)}；增减：${revenueAmount(row.mom.difference)}`"><span>{{revenueChange(row.mom)}}</span></el-tooltip></template></el-table-column>
                <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button link type="primary" @click="trackClient(row.key)">跟踪</el-button></template></el-table-column>
              </el-table>
              <el-pagination v-model:current-page="page" :page-size="20" :total="data.total" layout="total,prev,pager,next" @current-change="load" />
            </el-tab-pane>
            <el-tab-pane label="周期趋势／客户跟踪" name="trend">
              <AppForm :model="filters" inline><el-form-item label="跟踪客户"><el-select v-model="focusClient" filterable clearable placeholder="全部客户汇总" style="width:320px;max-width:100%" @change="load"><el-option v-for="item in data.client_options" :key="item.key" :label="item.name" :value="item.key" /></el-select></el-form-item></AppForm>
              <p class="revenue-help">{{focusName}} · 最近12个{{periodLabel}} · {{data.currency}}。鼠标移到柱形可查看金额；下表列出每期同比、环比。</p>
              <svg class="revenue-chart" viewBox="0 0 1000 210" role="img" :aria-label="`${focusName}营收趋势`"><line x1="30" :y1="chart.zero" x2="990" :y2="chart.zero" stroke="currentColor" opacity=".25" /><g v-for="(item,index) in chart.bars" :key="item.start"><title>{{item.label}}：{{data.currency}} {{revenueAmount(item.amount)}}</title><rect :x="42+index*79" :y="item.y" width="42" :height="Math.max(item.height,1)" rx="3" :fill="Number(item.amount)>=0?'#415a77':'#b45309'" /><text :x="63+index*79" y="199" text-anchor="middle" font-size="11">{{item.label.replace('年','/').replace('第','').replace('季度','季')}}</text></g></svg>
              <el-table :data="data.timeline" border max-height="400"><el-table-column prop="label" label="周期" min-width="130" /><el-table-column label="日期范围" min-width="200"><template #default="{row}">{{row.start}} 至 {{row.end}}</template></el-table-column><el-table-column label="营收金额" min-width="130" align="right"><template #default="{row}">{{revenueAmount(row.amount)}}<el-tag v-if="row.missing" size="small" type="warning">待补</el-tag></template></el-table-column><el-table-column label="同比" min-width="110"><template #default="{row}">{{revenueChange(row.yoy)}}</template></el-table-column><el-table-column label="环比" min-width="110"><template #default="{row}">{{revenueChange(row.mom)}}</template></el-table-column></el-table>
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
    </div>
    <template #footer><span class="revenue-help">{{data?.generated_at?`统计时间：${formatBusinessDateTime(data.generated_at)}`:''}}</span><el-button @click="$emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {getTranslationRevenue} from '@/api/translationRevenue'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {revenuePeriods,revenueBases,rankShortcuts,amountShortcuts,revenueAmount,revenueChange,normalizedRange} from '@/utils/revenueStatistics'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AdvancedFilterPopover from './AdvancedFilterPopover.vue'
import AppForm from './AppForm.vue'

const props=defineProps({modelValue:Boolean,query:{type:Object,default:()=>({})},scopeLabel:{type:String,default:'全部客户'}})
defineEmits(['update:modelValue'])
const body=ref(),{fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const initial=()=>({period:'month',anchor:businessDateTimeInputValue().slice(0,10),currency:'CNY',keyword:'',rankMin:null,rankMax:null,amountMin:null,amountMax:null})
const filters=reactive(initial()),data=ref(null),error=ref(''),loading=ref(false),page=ref(1),activeTab=ref('ranking'),advancedVisible=ref(false),focusClient=ref('')
const storageKey=`translation-revenue-client-basis:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const modes=ref((()=>{try{const value=JSON.parse(localStorage.getItem(storageKey)||'{}');return Object.fromEntries(Object.entries(value).filter(([key,value])=>/^[a-f\d-]{36}$/i.test(key)&&['billing','excl','incl'].includes(value)))}catch{return {}}})())
let timer,controller,sequence=0
const currencies=computed(()=>[...new Set([filters.currency,...(data.value?.currencies||['CNY'])])])
const advancedCount=computed(()=>[filters.rankMin,filters.rankMax,filters.amountMin,filters.amountMax].filter(v=>v!=null&&v!=='').length)
const periodLabel=computed(()=>revenuePeriods.find(item=>item.value===filters.period)?.label||'月')
const focusName=computed(()=>data.value?.client_options?.find(item=>item.key===focusClient.value)?.name||'全部客户')
const rangeLabel=computed(()=>{const [r1,r2]=normalizedRange(filters.rankMin,filters.rankMax),[a1,a2]=normalizedRange(filters.amountMin,filters.amountMax);return [r1!=null||r2!=null?`排名 ${r1??1}–${r2??'不限'}名`:'',a1!=null||a2!=null?`${filters.currency} ${a1??'不限'}–${a2??'不限'}`:''].filter(Boolean).join('；')})
const chart=computed(()=>{const items=data.value?.timeline||[],values=items.map(item=>Number(item.amount)),max=Math.max(0,...values),min=Math.min(0,...values),span=max-min||1,zero=170*max/span+8;return {zero,bars:items.map(item=>{const amount=Number(item.amount);return {...item,y:amount>=0?zero-170*amount/span:zero,height:170*Math.abs(amount)/span}})}})
function params(){const [rankMin,rankMax]=normalizedRange(filters.rankMin,filters.rankMax),[amountMin,amountMax]=normalizedRange(filters.amountMin,filters.amountMax);return {period:filters.period,anchor:filters.anchor,currency:filters.currency,keyword:filters.keyword.trim()||undefined,rank_min:rankMin,rank_max:rankMax,amount_min:amountMin,amount_max:amountMax,client_basis:JSON.stringify(modes.value),focus_client:focusClient.value||undefined,skip:(page.value-1)*20,limit:20,manager_ids:props.query.manager_ids,only_mine:props.query.only_mine||false,client_id:props.query.client_id}}
async function load(){clearTimeout(timer);const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const result=await getTranslationRevenue(params(),{signal:controller.signal});if(current===sequence)data.value=result}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED'){data.value=null;error.value=getLocalizedErrorMessage(e,'营收统计加载失败')}}finally{if(current===sequence)loading.value=false}}
function search(){page.value=1;void load()}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;loading.value=false;if(!value.trim())search();else timer=setTimeout(search,400)}
function chooseRank(item){filters.rankMin=item.min;filters.rankMax=item.max;search()}
function chooseAmount(item){filters.amountMin=item.min;filters.amountMax=item.max;search()}
function clearRank(){filters.rankMin=null;filters.rankMax=null;search()}
function clearAmount(){filters.amountMin=null;filters.amountMax=null;search()}
function clearRanges(){filters.rankMin=null;filters.rankMax=null;filters.amountMin=null;filters.amountMax=null;search()}
function reset(){Object.assign(filters,initial());focusClient.value='';activeTab.value='ranking';search()}
function setBasis(id,value){if(!id)return;if(value==='billing')delete modes.value[id];else modes.value[id]=value;try{localStorage.setItem(storageKey,JSON.stringify(modes.value))}catch{}search()}
function trackClient(key){focusClient.value=key;activeTab.value='trend';void load()}
watch(()=>props.modelValue,visible=>{sequence++;controller?.abort();clearTimeout(timer);clearFieldSearch();advancedVisible.value=false;if(visible){data.value=null;reset()}else loading.value=false})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
</script>

<style scoped>
:global(.revenue-statistics-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.revenue-statistics-dialog>.el-dialog__header),:global(.revenue-statistics-dialog>.el-dialog__footer){flex:none}:global(.revenue-statistics-dialog>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.revenue-statistics-dialog>.el-dialog__footer){border-top:1px solid var(--el-border-color-light);background:#f8fafc;display:flex;align-items:center;justify-content:space-between;gap:12px}.revenue-query{display:flex;flex-wrap:wrap;gap:10px}.revenue-query :deep(.el-form-item){margin-right:0;margin-bottom:8px}.revenue-help{font-size:12px;color:var(--el-text-color-secondary);line-height:1.7}.revenue-shortcuts{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}.revenue-shortcuts .el-button+.el-button{margin-left:0}.revenue-shortcuts>span{font-size:12px}.revenue-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}.revenue-cards>div{padding:16px;border:1px solid var(--el-border-color-light);border-radius:8px;display:flex;flex-direction:column;gap:8px}.revenue-cards strong{font-size:24px;color:var(--el-text-color-primary)}.revenue-cards small,.revenue-cards span{font-size:12px;color:var(--el-text-color-secondary)}.revenue-period{margin:14px 0 0}.revenue-ranking-toolbar{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.revenue-ranking-toolbar>span{font-size:13px}.el-pagination{margin-top:12px}.revenue-range-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.revenue-range{display:flex;gap:8px;align-items:center;max-width:100%}.revenue-range .el-input-number{width:140px;max-width:42%}.revenue-chart{width:100%;height:auto;max-height:250px;color:var(--el-text-color-secondary)}@media(max-width:700px){.revenue-cards{grid-template-columns:1fr}.revenue-range-grid{grid-template-columns:1fr}.revenue-cards strong{font-size:20px}}
</style>
