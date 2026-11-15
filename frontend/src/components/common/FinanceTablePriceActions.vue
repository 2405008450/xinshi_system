<template>
  <el-popover v-model:visible="visible" title="客户参考价与单价同步" trigger="click" placement="left-start" :width="440" popper-class="finance-price-settings-popper" @show="onShow">
    <template #reference><el-button link type="primary" :disabled="busy" aria-label="客户参考价与单价同步">参考价／同步</el-button></template>
    <div v-loading="busy" class="table-price-actions">
      <small>{{row.orderNo}} · {{row.clientShortName||'当前客户'}}</small>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-button v-if="error" link :disabled="busy" @click="refresh">重新加载</el-button>
      <el-alert v-if="hasConflict" title="项目单价与客户参考价不同。请选择保留当前单价，或比较后采用客户参考价。" type="warning" :closable="false" />
      <el-button v-if="hasConflict" :disabled="busy" @click="visible=false">保留当前单价</el-button>
      <el-button :disabled="busy||!context?.node.clientId" @click="adopt">{{hasConflict?'比较并选择客户参考价':'选择客户参考价'}}</el-button>
      <small v-if="context&&!references.length">暂无完整匹配的客户参考价。</small>
      <SyncSameMonthPrices v-if="context" :project-id="row.rootId" :order-id="row.id" :source-order-no="context.node.orderNo || row.orderNo" :client-id="context.node.clientId" :version="context.data.version" :month="context.node.billingMonth" :disabled="busy||!context.node.prices?.length" :prepare="prepareSameMonth" @synced="synced" />
      <small v-if="context&&!context.node.billingMonth">尚未登记账单月份，不能同步同月订单。</small>
    </div>
  </el-popover>
  <CustomerReferencePriceDialog v-if="context" ref="pickerRef" :client-id="context.node.clientId" :client-name="row.clientShortName" :prices="context.node.prices" :matrix="context.node.wordCountMatrix" :language-pair="context.node.languagePair" :refresh-project="readCurrent" />
</template>

<script setup>
import {computed,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {getCustomerFinanceProject,saveCustomerFinanceProject} from '@/api/translationCustomerFinance'
import {referenceDraft,ratePayload} from '@/utils/customerTranslationRates'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import SyncSameMonthPrices from './SyncSameMonthPrices.vue'
import CustomerReferencePriceDialog from './CustomerReferencePriceDialog.vue'
import {priceMatch,expectedOrderPrices,replaceMatchedReference,hasCustomerRateConflict} from '@/utils/customerRateMatching'
const props=defineProps({row:Object,prepare:Function})
const emit=defineEmits(['saved'])
const visible=ref(false),busy=ref(false),error=ref(''),context=ref(null),pickerRef=ref()
const find=(node,id)=>node.id===id?node:(node.children||[]).map(child=>find(child,id)).find(Boolean)
const references=computed(()=>(context.value?.data.referencePrices?.items||[]).filter(reference=>expectedOrderPrices(context.value?.node.prices,context.value?.node.languagePair,context.value?.node.wordCountMatrix).some(price=>priceMatch(reference,price,context.value?.node.wordCountMatrix).matched)))
const hasConflict=computed(()=>context.value?.node.prices?.some(price=>hasCustomerRateConflict(price,references.value,context.value.node.wordCountMatrix)))
async function readCurrent(){
  if(props.prepare&&!await props.prepare())throw new Error('有单元格尚未保存，请先处理提示')
  const data=await getCustomerFinanceProject(props.row.rootId),node=find(data.item,props.row.id)
  if(!node)throw new Error('订单已变化，请刷新列表')
  if(node.pricingMode==='fixed')throw new Error('当前订单已改为固定收费，请刷新列表')
  context.value={data,node};return context.value
}
async function refresh(){busy.value=true;error.value='';try{await readCurrent()}catch(e){context.value=null;error.value=getLocalizedErrorMessage(e,e.message||'参考价加载失败')}finally{busy.value=false}}
function onShow(){if(!busy.value&&!error.value)void refresh()}
async function persist(current,prices){
  const {data,node}=current
  const result=await saveCustomerFinanceProject(props.row.rootId,{version:data.version,order_id:props.row.id,pricing_mode:node.pricingMode||'metric',currency:node.currency||'CNY',prices:prices.map(ratePayload),adjusted_total:node.adjustedTotal??null,adjusted_total_incl_tax:node.adjustedTotalInclTax??null,explanation:node.explanation||'',billing_month:node.billingMonth||null})
  const order = `订单 ${node.orderNo || props.row.orderNo}`
  const clientRates = `客户管理 · ${node.clientShortName || props.row.clientShortName || node.clientName || '当前客户'}的笔译报价`
  emit('saved',result)
  visible.value=false
  ElMessage.success(`已将${clientRates}同步至${order}`)
}
async function adopt(){
  if(busy.value)return;busy.value=true;error.value=''
  try{await readCurrent();visible.value=false;const choice=await pickerRef.value.confirm();if(!choice)return;const current=await readCurrent();const prices=expectedOrderPrices(current.node.prices,current.node.languagePair,current.node.wordCountMatrix).map(price=>({...price}));const index=replaceMatchedReference(prices,choice.price,current.node.wordCountMatrix);prices[index]={...referenceDraft(choice.price),id:prices[index].id,metric:prices[index].metric};await persist(current,prices)}
  catch(e){error.value=getLocalizedErrorMessage(e,e.message||'采用参考价失败');visible.value=true}
  finally{busy.value=false}
}
async function prepareSameMonth(){
  error.value=''
  try{const {data,node}=await readCurrent();visible.value=false;return {version:data.version,billing_month:node.billingMonth,order_id:props.row.id}}
  catch(e){error.value=getLocalizedErrorMessage(e,e.message||'同步准备失败');return false}
}
function synced(){visible.value=false;emit('saved')}
</script>

<style scoped>
.table-price-actions{display:grid;gap:10px;max-height:min(520px,calc(100vh - 120px));overflow-y:auto}.table-price-actions>.el-button{margin-left:0;justify-self:start;white-space:normal;height:auto;min-height:32px}.table-price-actions small{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}
</style>
