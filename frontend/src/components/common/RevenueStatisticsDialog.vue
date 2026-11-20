<template>
  <DraggableFormDialog :model-value="modelValue" class="revenue-statistics-dialog" width="min(1320px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" @update:model-value="$emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="营收统计" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
      <AppForm data-auto-draft="off" :model="filters" inline class="revenue-query" @submit.prevent="search">
        <el-form-item label="项目类型"><el-select v-model="filters.projectType" style="width:110px" @change="changeProjectType"><el-option v-for="item in projectTypes" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item>
        <el-form-item label="统计周期"><el-select v-model="filters.period" style="width:100px" @change="search"><el-option v-for="item in revenuePeriods" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item>
        <el-form-item label="所属日期"><el-date-picker v-model="filters.anchor" type="date" value-format="YYYY-MM-DD" :clearable="false" style="width:150px" @change="search" /></el-form-item>
        <el-form-item label="币种"><el-select v-model="filters.currency" style="width:100px" @change="search"><el-option v-for="currency in currencies" :key="currency" :value="currency" :label="currency" /></el-select></el-form-item>
        <el-form-item label="客户经理">
          <CustomerDepartmentManagerSelect :model-value="filters.managerIds" placeholder="全体" style="width:180px" @update:model-value="changeManagers" />
        </el-form-item>
        <el-form-item><el-button :loading="loading" @click="search">查询</el-button><el-button @click="reset">重置</el-button><AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearRanges" @reset="reset">
          <AppForm data-auto-draft="off" :model="filters" label-position="top" @submit.prevent="search">
            <div class="revenue-range-grid"><el-form-item label="排名区间"><div class="revenue-range"><el-input-number v-model="filters.rankMin" :min="1" :precision="0" :controls="false" placeholder="起始名次" aria-label="起始名次" @change="search" /><span>至</span><el-input-number v-model="filters.rankMax" :min="1" :precision="0" :controls="false" placeholder="结束名次" aria-label="结束名次" @change="search" /></div></el-form-item>
            <el-form-item :label="`金额范围（${filters.currency}）`"><div class="revenue-range"><el-input-number v-model="filters.amountMin" :precision="2" :controls="false" placeholder="最低金额" aria-label="最低金额" @change="search" /><span>至</span><el-input-number v-model="filters.amountMax" :precision="2" :controls="false" placeholder="最高金额" aria-label="最高金额" @change="search" /></div></el-form-item></div>
            <p class="revenue-help">区间包含两端；起止值倒序时自动按大小归一。排名、金额条件同时生效。</p>
          </AppForm>
        </AdvancedFilterPopover></el-form-item>
      </AppForm>
      <p class="revenue-help">按订单日期归属；无法识别订单日期时采用项目已有业务日期。周为周一至周日；按完整自然周期比较，当前周期可能尚未结束。币种分别统计。统计口径按客户选择后相加；选择仅影响本窗口并按当前用户记忆。</p>
      <details class="revenue-shortcut-section">
        <summary>排名与金额快捷筛选</summary>
        <div class="revenue-shortcuts">
          <span>排名快捷：</span>
          <el-button v-for="item in rankShortcuts" :key="item.label" size="small" :aria-pressed="activeRankShortcut === item" @click="chooseShortcut('rank',item)">{{item.label}}</el-button>
          <el-button size="small" @click="clearRank">不限排名</el-button>
        </div>
        <div class="revenue-shortcuts">
          <span>金额快捷：</span>
          <el-button v-for="item in amountShortcuts" :key="item.min" class="revenue-amount-shortcut"
            :aria-pressed="activeAmountShortcut === item" @click="chooseShortcut('amount',item)">
            <span class="revenue-amount-shortcut-content">
              <strong>{{ item.max == null ? `${item.min}以上` : `${item.min}–${item.max}` }}</strong>
              <span>{{ item.customers }} 位客户 · {{ amountShare(item.customers) }}</span>
            </span>
          </el-button>
          <el-button size="small" @click="clearAmount">不限金额</el-button>
        </div>
        <p v-if="data?.amount_shortcut_total != null" class="revenue-help">
          占比按当前查询范围内参与排名的 {{ data.amount_shortcut_total }} 位客户计算，金额档位包含两端。
        </p>
      </details>
      <p v-if="rangeLabel" class="revenue-help">已选：{{rangeLabel}} <el-button link @click="clearRanges">清空区间条件</el-button></p>
      <el-alert v-if="error" :title="data ? `${error}，当前显示上次查询结果` : error" type="error" :closable="false">
        <el-button link @click="load()">重新查询</el-button>
      </el-alert>
      <div v-loading="loading && !!data" :aria-busy="loading">
        <div v-if="loading && !data" class="revenue-initial-loading" role="status">
          <p>正在汇总营收数据…</p>
          <el-skeleton :rows="4" animated />
        </div>
        <template v-if="data">
          <h4 class="revenue-period">{{data.period.label}} · {{data.period.start}} 至 {{data.period.end}} <el-tag v-if="data.partial_period" type="warning" size="small">周期未结束</el-tag></h4>
          <div class="revenue-cards"><div><small>总营收 · {{data.currency}}</small><strong>{{revenueAmount(data.overall.amount)}}</strong><span>{{data.overall.customers}} 个有计费金额客户</span></div><div><small>同比 · {{data.last_year?.label||'无可比周期'}}</small><strong>{{revenueChange(data.overall.yoy)}}</strong><span>基期 {{revenueAmount(data.overall.yoy.amount)}} · 增减 {{revenueAmount(data.overall.yoy.difference)}}</span></div><div><small>环比 · {{data.previous.label}}</small><strong>{{revenueChange(data.overall.mom)}}</strong><span>基期 {{revenueAmount(data.overall.mom.amount)}} · 增减 {{revenueAmount(data.overall.mom.difference)}}</span></div></div>
          <section v-if="data.project_type_totals" class="revenue-project-comparison" aria-label="本期项目对比">
            <h3>本期项目对比</h3>
            <el-table :data="data.project_type_totals" row-key="module" border size="small">
              <el-table-column label="项目类型" min-width="105">
                <template #default="{row}">{{ projectTypes.find(type => type.value === row.module)?.label }}</template>
              </el-table-column>
              <el-table-column prop="customers" label="客户数" min-width="90" align="right" />
              <el-table-column prop="orders" label="订单数" min-width="90" align="right" />
              <el-table-column :label="`总金额（${data.currency}）`" min-width="125" align="right">
                <template #default="{row}">{{ revenueAmount(row.amount) }}</template>
              </el-table-column>
            </el-table>
            <p class="revenue-help">客户数按类型去重，仅统计已关联客户。订单数含待补订单，母子订单按母单计数。总金额按所选币种及客户统计口径汇总。</p>
          </section>
          <el-alert v-if="data.overall.missing||data.missing_date||data.fallback_date" type="warning" :closable="false" :title="`本期 ${data.overall.missing} 个项目金额待补；范围内 ${data.fallback_date} 个项目采用备用业务日期，另有 ${data.missing_date} 个项目无可用日期而未计入。金额待补时统计可能不完整。`" />
          <el-tabs v-model="activeTab">
            <el-tab-pane label="客户营收排名" name="ranking">
              <div class="revenue-ranking-toolbar"><el-input v-model="filters.keyword" clearable placeholder="客户全称或简称，多关键词搜索" style="width:290px;max-width:100%" @input="queueSearch" @keyup.enter="search" /><span>匹配 {{data.total}} / {{data.ranked_customers}} 个客户 · 筛选后合计 {{data.currency}} {{revenueAmount(data.filtered_amount)}}</span></div>
              <p class="revenue-help">排名按本期金额降序，同额按客户名称及编号排列；区间筛选后保留原排名。上期或去年同期有记录的客户本期无营收时仍列出。上方总营收和趋势不受排名、金额、客户关键词筛选影响。</p>
              <el-table :data="data.items" border row-key="key" empty-text="暂无匹配客户" max-height="440">
                <el-table-column prop="rank" label="排名" width="70" /><el-table-column prop="client_name" label="客户名称" min-width="170" show-overflow-tooltip /><el-table-column label="统计口径" width="170"><template #default="{row}"><el-select :model-value="row.basis" :disabled="!row.client_id" @change="value=>setBasis(row.client_id,value)"><el-option v-for="item in revenueBases" :key="item.value" :label="item.label" :value="item.value" /></el-select></template></el-table-column>
                <el-table-column label="本期营收" min-width="145" align="right">
                  <template #default="{row}">
                    <RevenueOrderDetails :row="row" :query="orderDetailQuery" :period-label="data.period.label" />
                    <el-popover v-if="row.missing" trigger="click" placement="left" :width="560"
                      popper-class="revenue-missing-popover" :title="`${row.client_name} · 本期待补`">
                      <template #reference>
                        <el-button link type="warning" size="small" :aria-label="`查看 ${row.client_name} 本期待补明细`">
                          待补 {{row.missing}}
                        </el-button>
                      </template>
                      <el-table :data="row.missing_orders || []" border size="small" max-height="380" empty-text="暂无待补明细">
                        <el-table-column prop="order_no" label="订单号" min-width="125" />
                        <el-table-column prop="project_name" label="项目名称" min-width="135" />
                        <el-table-column label="待补内容" min-width="150">
                          <template #default="{row: order}">{{order.reasons.join('、')}}</template>
                        </el-table-column>
                      </el-table>
                    </el-popover>
                  </template>
                </el-table-column>
                <el-table-column prop="projects" label="计费项目数" width="100" />
                <el-table-column label="同比" min-width="125"><template #default="{row}"><el-tooltip :content="`去年同期：${revenueAmount(row.yoy.amount)}；增减：${revenueAmount(row.yoy.difference)}`"><span>{{revenueChange(row.yoy)}}</span></el-tooltip></template></el-table-column>
                <el-table-column label="环比" min-width="125"><template #default="{row}"><el-tooltip :content="`上期：${revenueAmount(row.mom.amount)}；增减：${revenueAmount(row.mom.difference)}`"><span>{{revenueChange(row.mom)}}</span></el-tooltip></template></el-table-column>
                <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button link type="primary" @click="trackClient(row.key)">跟踪</el-button></template></el-table-column>
              </el-table>
              <el-pagination :current-page="page" :page-size="20" :total="data.total" :disabled="loading" layout="total,prev,pager,next" @update:current-page="changePage" />
            </el-tab-pane>
            <el-tab-pane label="周期趋势／客户跟踪" name="trend" lazy>
              <AppForm data-auto-draft="off" :model="filters" inline><el-form-item label="跟踪客户"><el-select v-model="focusClient" filterable clearable placeholder="全部客户汇总" style="width:320px;max-width:100%" @change="load"><el-option v-for="item in data.client_options" :key="item.key" :label="item.name" :value="item.key" /></el-select></el-form-item></AppForm>
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
import {revenuePeriods,revenueBases,rankShortcuts,revenueAmount,revenueChange,normalizedRange} from '@/utils/revenueStatistics'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AdvancedFilterPopover from './AdvancedFilterPopover.vue'
import AppForm from './AppForm.vue'
import CustomerDepartmentManagerSelect from './CustomerDepartmentManagerSelect.vue'
import RevenueOrderDetails from './RevenueOrderDetails.vue'

const props=defineProps({modelValue:Boolean,clientId:[String,Number]})
defineEmits(['update:modelValue'])
const body=ref(),{fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const projectTypes = [{value:'all',label:'全部项目'},{value:'translation',label:'笔译'},{value:'interpretation',label:'口译'},{value:'annotation',label:'标注'},{value:'recruitment',label:'招聘'}]
const initial=()=>({projectType:'all',period:'month',anchor:businessDateTimeInputValue().slice(0,10),currency:'CNY',managerIds:[],keyword:'',rankMin:null,rankMax:null,amountMin:null,amountMax:null})
const filters=reactive(initial()),data=ref(null),error=ref(''),loading=ref(false),page=ref(1),activeTab=ref('ranking'),advancedVisible=ref(false),focusClient=ref('')
const displayedPeriod = ref('month')
const orderDetailQuery = ref({})
const storageKey=`translation-revenue-client-basis:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const modes=ref((()=>{try{const value=JSON.parse(localStorage.getItem(storageKey)||'{}');return Object.fromEntries(Object.entries(value).filter(([key,value])=>/^[a-f\d-]{36}$/i.test(key)&&['billing','excl','incl'].includes(value)))}catch{return {}}})())
let timer, controller, pendingKey, sequence = 0
const currencies=computed(()=>[...new Set([filters.currency,...(data.value?.currencies||['CNY'])])])
const advancedCount=computed(()=>[filters.rankMin,filters.rankMax,filters.amountMin,filters.amountMax].filter(v=>v!=null&&v!=='').length)
const rankRange=computed(()=>normalizedRange(filters.rankMin,filters.rankMax))
const amountRange=computed(()=>normalizedRange(filters.amountMin,filters.amountMax))
const amountShortcuts=computed(()=>data.value?.amount_shortcuts ?? [])
const percentFormatter = new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 2 })
const activeRankShortcut=computed(()=>activeShortcut(rankShortcuts,rankRange.value,amountRange.value))
const activeAmountShortcut=computed(()=>activeShortcut(amountShortcuts.value,amountRange.value,rankRange.value))
const periodLabel=computed(()=>revenuePeriods.find(item=>item.value===displayedPeriod.value)?.label||'月')
const focusName=computed(()=>data.value?.client_options?.find(item=>item.key===data.value?.focus_client)?.name||'全部客户')
const rangeLabel=computed(()=>{const [r1,r2]=normalizedRange(filters.rankMin,filters.rankMax),[a1,a2]=normalizedRange(filters.amountMin,filters.amountMax);return [r1!=null||r2!=null?`排名 ${r1??1}–${r2??'不限'}名`:'',a1!=null||a2!=null?`${filters.currency} ${a1??'不限'}–${a2??'不限'}`:''].filter(Boolean).join('；')})
const chart=computed(()=>{const items=data.value?.timeline||[],values=items.map(item=>Number(item.amount)),max=Math.max(0,...values),min=Math.min(0,...values),span=max-min||1,zero=170*max/span+8;return {zero,bars:items.map(item=>{const amount=Number(item.amount);return {...item,y:amount>=0?zero-170*amount/span:zero,height:170*Math.abs(amount)/span}})}})
function params(){const [rankMin,rankMax]=normalizedRange(filters.rankMin,filters.rankMax),[amountMin,amountMax]=normalizedRange(filters.amountMin,filters.amountMax);return {project_type:filters.projectType,period:filters.period,anchor:filters.anchor,currency:filters.currency,keyword:filters.keyword.trim()||undefined,rank_min:rankMin,rank_max:rankMax,amount_min:amountMin,amount_max:amountMax,client_basis:JSON.stringify(modes.value),focus_client:focusClient.value||undefined,skip:(page.value-1)*20,limit:20,manager_ids:filters.managerIds.length?filters.managerIds:undefined,client_id:props.clientId}}
async function load() {
  clearTimeout(timer)
  const query = params()
  const key = JSON.stringify(query)
  if (pendingKey === key) return
  const current = ++sequence
  controller?.abort()
  controller = new AbortController()
  pendingKey = key
  loading.value = true
  error.value = ''
  try {
    const result = await getTranslationRevenue(query, { signal: controller.signal })
    if (current !== sequence) return
    const lastPage = Math.max(1, Math.ceil(result.total / query.limit))
    if (page.value > lastPage) {
      page.value = lastPage
      return load()
    }
    displayedPeriod.value = query.period
    const { project_type, period, anchor, currency, manager_ids, client_id } = query
    const detailQuery = { project_type, period, anchor, currency, manager_ids, client_id }
    if (JSON.stringify(orderDetailQuery.value) !== JSON.stringify(detailQuery)) {
      orderDetailQuery.value = detailQuery
    }
    data.value = result
  } catch (e) {
    if (current === sequence && e.code !== 'ERR_CANCELED') {
      error.value = getLocalizedErrorMessage(e, '营收统计加载失败')
    }
  } finally {
    if (current === sequence) {
      pendingKey = undefined
      loading.value = false
    }
  }
}
function changePage(value) {
  if (loading.value || value === page.value) return
  page.value = value
  void load()
}
function search(){page.value=1;void load()}
function changeProjectType(){focusClient.value='';search()}
function changeManagers(ids){
  filters.managerIds=ids
  focusClient.value=''
  search()
}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;pendingKey=undefined;loading.value=false;if(!value.trim())search();else timer=setTimeout(search,400)}
function activeShortcut(items,[min,max],otherRange){
  if (otherRange.some(value=>value!=null)) return
  return items.find(item=>item.min===min&&(item.max??undefined)===max)
}
function amountShare(customers) {
  const total = data.value?.amount_shortcut_total
  return percentFormatter.format(total ? customers / total : 0)
}
function chooseShortcut(kind,item){
  if (kind==='rank') {
    Object.assign(filters,{rankMin:item.min,rankMax:item.max,amountMin:null,amountMax:null})
  } else {
    Object.assign(filters,{rankMin:null,rankMax:null,amountMin:item.min,amountMax:item.max})
    activeTab.value='ranking'
  }
  search()
}
function clearRank(){filters.rankMin=null;filters.rankMax=null;search()}
function clearAmount(){filters.amountMin=null;filters.amountMax=null;search()}
function clearRanges(){filters.rankMin=null;filters.rankMax=null;filters.amountMin=null;filters.amountMax=null;search()}
function restoreFilterDefaults(){Object.assign(filters,initial());focusClient.value='';activeTab.value='ranking'}
function reset(){restoreFilterDefaults();if(props.modelValue)search()}
function setBasis(id,value){if(!id)return;if(value==='billing')delete modes.value[id];else modes.value[id]=value;try{localStorage.setItem(storageKey,JSON.stringify(modes.value))}catch{}search()}
function trackClient(key){focusClient.value=key;activeTab.value='trend';void load()}
watch(()=>props.modelValue,visible=>{sequence++;controller?.abort();clearTimeout(timer);pendingKey=undefined;clearFieldSearch();advancedVisible.value=false;data.value=null;restoreFilterDefaults();if(visible)search();else loading.value=false})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
</script>

<style scoped>
:global(.revenue-missing-popover){max-width:calc(100vw - 32px)}
.revenue-shortcut-section>summary{width:fit-content;cursor:pointer;font-size:13px;color:var(--el-text-color-regular)}
.revenue-shortcuts .el-button[aria-pressed="true"]{background:#000;border-color:#000;color:#fff}
.revenue-shortcuts .revenue-amount-shortcut { height: auto; padding: 8px 12px; }
.revenue-amount-shortcut-content { display: grid; gap: 4px; line-height: 1.3; text-align: left; }
.revenue-amount-shortcut-content > span { font-size: 12px; }
.revenue-project-comparison { margin: 12px 0; }
.revenue-project-comparison h3 { margin: 0 0 8px; font-size: 15px; }
:global(.el-dialog.revenue-statistics-dialog) { height: 90vh; box-sizing: border-box; }
:global(.revenue-statistics-dialog > .el-dialog__body) { scrollbar-gutter: stable; overflow-anchor: none; }
.revenue-initial-loading { padding: 16px 0; color: var(--el-text-color-secondary); }
:global(.revenue-statistics-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.revenue-statistics-dialog>.el-dialog__header),:global(.revenue-statistics-dialog>.el-dialog__footer){flex:none}:global(.revenue-statistics-dialog>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.revenue-statistics-dialog>.el-dialog__footer){border-top:1px solid var(--el-border-color-light);background:#f8fafc;display:flex;align-items:center;justify-content:space-between;gap:12px}.revenue-query{display:flex;flex-wrap:wrap;gap:10px}.revenue-query :deep(.el-form-item){margin-right:0;margin-bottom:8px}.revenue-help{font-size:12px;color:var(--el-text-color-secondary);line-height:1.7}.revenue-shortcuts{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}.revenue-shortcuts .el-button+.el-button{margin-left:0}.revenue-shortcuts>span{font-size:12px}.revenue-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}.revenue-cards>div{padding:16px;border:1px solid var(--el-border-color-light);border-radius:8px;display:flex;flex-direction:column;gap:8px}.revenue-cards strong{font-size:24px;color:var(--el-text-color-primary)}.revenue-cards small,.revenue-cards span{font-size:12px;color:var(--el-text-color-secondary)}.revenue-period{margin:14px 0 0}.revenue-ranking-toolbar{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.revenue-ranking-toolbar>span{font-size:13px}.el-pagination{margin-top:12px}.revenue-range-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.revenue-range{display:flex;gap:8px;align-items:center;max-width:100%}.revenue-range .el-input-number{width:140px;max-width:42%}.revenue-chart{width:100%;height:auto;max-height:250px;color:var(--el-text-color-secondary)}@media(max-width:700px){.revenue-cards{grid-template-columns:1fr}.revenue-range-grid{grid-template-columns:1fr}.revenue-cards strong{font-size:20px}}
</style>

<style>
@media (max-width: 700px) {
  .revenue-statistics-dialog:not(.is-maximized):not(.is-fullscreen) {
    width: calc(100vw - 32px) !important;
    max-width: calc(100vw - 32px);
  }
}
</style>
