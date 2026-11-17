<template>
  <div class="rate-differences">
    <el-button v-if="clientId" :disabled="disabled || busy" @click="visible=true;load()">查看项目已登记单价</el-button>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="differenceCount" type="warning" :closable="false" :title="`已登记项目中有 ${differenceCount} 条单价与客户信息不一致`"><el-button type="warning" link :disabled="disabled" @click="visible=true;load()">{{module==='translation'?'查看订单差异':'查看差异并选择同步'}}</el-button></el-alert>
    <p v-else-if="!loading&&!error">{{ready?'已登记项目单价与客户信息一致':'客户单价存储尚未初始化'}}</p>
    <DraggableFormDialog v-model="visible" append-to-body class="customer-rate-differences-dialog" width="min(1200px, calc(100vw - 32px))" top="5vh" title="客户与项目单价差异" :close-on-click-modal="false" :before-close="close">
      <p v-if="module==='annotation'">逐条核对标注类型、货币、单位及金额，确认后将所选项目单价引入客户资料，项目原报价保留。</p>
      <p v-else-if="module==='translation'">订单单价差异自动记入客户单价的修改记录。保存客户参考价会更新匹配的订单。</p>
      <p v-else>客户参考价自动带入项目。项目中单独调整的价格予以保留；同步前请核对方向、货币和单位。数量、加班费、调整后总价及说明保持原值。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-table v-loading="loading||busy" :data="items" border row-key="order_id"
        :expand-row-keys="expandedOrders" @expand-change="onOrderExpand">
        <el-table-column label="订单号" min-width="230">
          <template #default="{row}">
            <span v-if="row.direction_group">{{row.language_directions[0]}}（{{row.children.length}} 个下级订单）</span>
            <span v-else>{{row.order_no}}</span>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目名称" min-width="160" />
        <el-table-column label="客户信息单价" min-width="260">
          <template #default="{row}"><span class="rate-text">{{describeOrder(row,'customer_rates')}}</span></template>
        </el-table-column>
        <el-table-column label="已登记项目单价" min-width="260">
          <template #default="{row}"><span class="rate-text">{{describeOrder(row,'project_rates')}}</span></template>
        </el-table-column>
        <el-table-column v-if="module!=='translation'" label="同步选择" fixed="right" width="190">
          <template #default="{row}">
            <el-button v-if="canWriteProjects && module!=='annotation'" link type="primary" :disabled="disabled||busy||!row.customer_rates.length" @click="synchronize(row,'client_to_project')">客户单价 → 此订单</el-button>
            <el-button v-if="canWriteClients" link type="warning" :disabled="disabled||busy||Boolean(row.sync_blocked_reason)" @click="synchronize(row,'project_to_client')">此订单单价 → 客户</el-button>
            <small v-if="row.sync_blocked_reason">{{row.sync_blocked_reason}}</small>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next" @current-change="load" />
      <template #footer><el-button :disabled="busy" @click="load">刷新差异</el-button><el-button :disabled="busy" @click="visible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {computed,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {getCustomerRateDifferences,synchronizeCustomerRates} from '@/api/customerFinanceSync'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {financeSummary} from '@/utils/interpretationCustomerFinance'
import {taxPriceSummary} from '@/utils/taxPrices'
import {annotationProjectTypeOptions} from '@/utils/annotationCatalog'
import {settlementUnitOptions,settlementLabel} from '@/utils/talentSettlement'
import {resolvedBasisLabel} from '@/utils/translationQuantityBasis'
const props=defineProps({module:{type:String,required:true},subClientId:String,clientId:{type:[String,Number],default:''},revision:{type:Number,default:0},disabled:Boolean})
const emit=defineEmits(['saved'])
const canWriteProjects=hasPermission('projects:write'),canWriteClients=hasPermission('clients:write')
const visible=ref(false),items=ref([]),page=ref(1),total=ref(0),loading=ref(false),busy=ref(false),error=ref(''),ready=ref(true)
const differenceCount=ref(0)
const expansionOverrides=ref(new Map())
const expandedOrders=computed(()=>{
  const keys=[]
  function visit(rows){
    for(const row of rows){
      if(!row.children?.length)continue
      if(expansionOverrides.value.get(row.order_id) ?? row.expand_by_default)keys.push(row.order_id)
      visit(row.children)
    }
  }
  visit(items.value)
  return keys
})
function onOrderExpand(row,expanded){
  if(typeof expanded==='boolean')expansionOverrides.value.set(row.order_id,expanded)
}
let sequence=0,controller
function describe(rows){
  if(props.module==='annotation')return rows.map(row=>`${settlementLabel(annotationProjectTypeOptions,row.project_type)}：${taxPriceSummary(row.tax_prices,row.currency,settlementLabel(settlementUnitOptions,row.unit),false)||('原单价（税口径未确认） '+row.currency+' '+row.amount+'/'+settlementLabel(settlementUnitOptions,row.unit))}`).join('\n')||'未登记匹配的客户单价'
  if(props.module==='interpretation')return financeSummary({rates:rows.map(row=>({...row,quantity:1}))})
  return rows.map(row=>{
    const basis=resolvedBasisLabel(row.metric,{dimension:row.quantity_dimension,metric:row.quantity_metric})
    const unit=`${Number(row.unit_size)} ${basis}`
    const summary=taxPriceSummary(row.tax_prices,row.currency,unit,false)||`原参考价（税口径未确认） ${row.currency} ${row.amount}/${unit}`
    const note=row.metric==='customer_auto'&&row.quantity_metric?' · 系统自动选择':''
    return `${row.language_pair}：${summary}${note}`
  }).join('\n')||'未登记匹配方向的单价'
}
function describeOrder(row,field){
  if(row[field])return describe(row[field])
  const summaries=new Set()
  function visit(order){
    if(order[field])summaries.add(describe(order[field]))
    for(const child of order.children || [])visit(child)
  }
  visit(row)
  if(summaries.size===1)return summaries.values().next().value
  return summaries.size ? '有多种单价，展开查看' : '—'
}
async function load(){
  if(!props.clientId)return
  const seq=++sequence
  controller?.abort()
  controller=new AbortController()
  loading.value=true
  error.value=''
  try{
    const data=await getCustomerRateDifferences(props.module,props.clientId,page.value,controller.signal,props.subClientId)
    if(seq!==sequence)return
    items.value=data.items
    total.value=data.total
    differenceCount.value=data.difference_count ?? data.total
    ready.value=data.ready
    if(page.value>1&&!items.value.length){
      page.value=Math.max(1,Math.ceil(total.value/10))
      void load()
    }
  }catch(e){
    if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'单价差异加载失败')
  }finally{
    if(seq===sequence)loading.value=false
  }
}
async function synchronize(row,direction){if(busy.value||props.disabled)return;const message=direction==='project_to_client'?(props.module==='annotation'?`确认将订单 ${row.order_no} 的这条单价引入客户资料？同类型、货币和单位的现有客户单价将更新，项目原报价保留。`:`确认将订单 ${row.order_no} 的以下单价同步至${props.subClientId?'子客户':'客户'}参考价？匹配的项目会按参考价规则自动更新。`):`确认以${props.subClientId?'子客户':'客户'}参考价更新订单 ${row.order_no}？`;
  try{await ElMessageBox.confirm(`${message}\n\n${describe(direction==='project_to_client'?row.project_rates:row.customer_rates)}`,'确认同步单价',{type:'warning',confirmButtonText:'确认同步',cancelButtonText:'取消'})}catch{return}
  busy.value=true;try{await synchronizeCustomerRates(props.module,props.clientId,{project_id:row.project_id,order_id:row.order_id,version:row.version,customer_version:row.customer_version,direction,confirmed:true,...(props.module==='translation'?{sub_client_id:props.subClientId||null}:{})});ElMessage.success(props.module==='annotation'?'项目单价已引入客户资料':'单价已同步并保留调整记录');await load();emit('saved')}catch(e){error.value=getLocalizedErrorMessage(e,'同步失败，请刷新差异后重新确认')}finally{busy.value=false}}
function close(done){if(busy.value)return;if(typeof done==='function')done();else visible.value=false}
watch(()=>[props.clientId,props.subClientId,props.module,props.revision],()=>{page.value=1;void load()},{immediate:true})
watch(()=>[props.clientId,props.module,visible.value],()=>expansionOverrides.value.clear())
function refreshTranslation(event){
  if(props.module==='translation'&&event.detail?.clientId===String(props.clientId))void load()
}
onMounted(()=>{
  window.addEventListener('customer-order-finance-saved',refreshTranslation)
  window.addEventListener('translation-finance-changed',refreshTranslation)
})
onBeforeUnmount(()=>{
  sequence++;controller?.abort()
  window.removeEventListener('customer-order-finance-saved',refreshTranslation)
  window.removeEventListener('translation-finance-changed',refreshTranslation)
})
</script>
<style scoped>
.rate-differences{margin:12px 0}.rate-text{white-space:pre-wrap;overflow-wrap:anywhere}p{font-size:12px;color:#64748b}.el-pagination{margin-top:12px}:global(.customer-rate-differences-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-rate-differences-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.customer-rate-differences-dialog .el-dialog__header),:global(.customer-rate-differences-dialog .el-dialog__footer){flex-shrink:0}:global(.customer-rate-differences-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
