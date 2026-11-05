<template>
  <el-popover v-model:visible="visible" title="客户参考价与单价同步" trigger="click" placement="left-start" :width="440" popper-class="finance-price-settings-popper" @show="onShow">
    <template #reference><el-button link type="primary" :disabled="busy" aria-label="客户参考价与单价同步">参考价／同步</el-button></template>
    <div v-loading="busy" class="table-price-actions">
      <small>{{row.orderNo}} · {{row.clientShortName||'当前客户'}}</small>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-button v-if="error" link :disabled="busy" @click="refresh">重新加载</el-button>
      <el-button :disabled="busy||!context?.node.clientId" @click="adopt">采用最新客户参考价</el-button>
      <small>{{references.length?'核对语种、单位、币种及计价数量后，手动选用报价。':'暂无完整匹配报价，可打开客户报价查看或编辑。'}}</small>
      <el-button v-if="canWriteClients" :disabled="busy||!context?.node.clientId||!context?.node.prices?.length" @click="syncClient">同步单价至客户信息…</el-button>
      <small v-if="canWriteClients">先比较现有参考价，确认后同步本订单已保存的单价。</small>
      <SyncSameMonthPrices :project-id="row.rootId" :order-id="row.id" :client-id="context?.node.clientId" :version="context?.data.version" :month="context?.node.billingMonth" :disabled="busy||!context?.node.prices?.length" :prepare="prepareSameMonth" @synced="synced" />
      <small v-if="context&&!context.node.billingMonth">尚未登记账单月份，不能同步同月订单。</small>
    </div>
  </el-popover>
  <CustomerReferencePriceDialog ref="pickerRef" :client-id="context?.node.clientId" :client-name="row.clientShortName" :prices="context?.node.prices" :matrix="context?.node.wordCountMatrix" :language-pair="context?.node.languagePair" :refresh-project="readCurrent" />
  <CustomerRateSyncPreview ref="previewRef" :client-id="context?.node.clientId" :client-name="row.clientShortName" :prices="context?.node.prices||[]" :matrix="context?.node.wordCountMatrix" :refresh-project="readCurrent" />
</template>

<script setup>
import {computed,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {getCustomerFinanceProject,saveCustomerFinanceProject} from '@/api/translationCustomerFinance'
import {defaultRateMetric,referenceDraft,ratePayload} from '@/utils/customerTranslationRates'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import SyncSameMonthPrices from './SyncSameMonthPrices.vue'
import CustomerRateSyncPreview from './CustomerRateSyncPreview.vue'
import CustomerReferencePriceDialog from './CustomerReferencePriceDialog.vue'
import {priceMatch,expectedOrderPrices,replaceMatchedReference} from '@/utils/customerRateMatching'
const props=defineProps({row:Object,prepare:Function})
const emit=defineEmits(['saved'])
const visible=ref(false),busy=ref(false),error=ref(''),context=ref(null),previewRef=ref(),pickerRef=ref()
const canWriteClients=hasPermission('clients:write')
const find=(node,id)=>node.id===id?node:(node.children||[]).map(child=>find(child,id)).find(Boolean)
const references=computed(()=>(context.value?.data.referencePrices?.items||[]).filter(reference=>expectedOrderPrices(context.value?.node.prices,context.value?.node.languagePair,context.value?.node.wordCountMatrix).some(price=>priceMatch(reference,price,context.value?.node.wordCountMatrix).matched)))
async function readCurrent(){
  if(props.prepare&&!await props.prepare())throw new Error('有单元格尚未保存，请先处理提示')
  const data=await getCustomerFinanceProject(props.row.rootId),node=find(data.item,props.row.id)
  if(!node)throw new Error('订单已变化，请刷新列表')
  if(node.pricingMode==='fixed')throw new Error('当前订单已改为固定收费，请刷新列表')
  context.value={data,node};return context.value
}
async function refresh(){busy.value=true;error.value='';try{await readCurrent()}catch(e){context.value=null;error.value=getLocalizedErrorMessage(e,e.message||'参考价加载失败')}finally{busy.value=false}}
function onShow(){if(!busy.value&&!error.value)void refresh()}
async function persist(current,prices,sync=false,libraryVersion){
  const {data,node}=current
  const result=await saveCustomerFinanceProject(props.row.rootId,{version:data.version,order_id:props.row.id,pricing_mode:node.pricingMode||'metric',currency:node.currency||'CNY',prices:prices.map(ratePayload),adjusted_total:sync?node.adjustedTotal??null:null,adjusted_total_incl_tax:node.adjustedTotalInclTax??null,explanation:node.explanation||'',billing_month:node.billingMonth||null,update_library:sync,sync_confirmed:sync,library_version:libraryVersion})
  emit('saved',result);visible.value=false;ElMessage.success(sync?'单价已同步至客户信息，并保留修改记录':'已采用最新客户参考价并保存')
}
async function adopt(){
  if(busy.value)return;busy.value=true;error.value=''
  try{await readCurrent();visible.value=false;const choice=await pickerRef.value.confirm();if(!choice)return;const current=await readCurrent();const prices=expectedOrderPrices(current.node.prices,current.node.languagePair,current.node.wordCountMatrix).map(price=>({...price}));const index=replaceMatchedReference(prices,choice.price,current.node.wordCountMatrix);prices[index]={...referenceDraft(choice.price),id:prices[index].id,metric:prices[index].metric};await persist(current,prices)}
  catch(e){error.value=getLocalizedErrorMessage(e,e.message||'采用参考价失败');visible.value=true}
  finally{busy.value=false}
}
async function syncClient(){
  if(busy.value)return;busy.value=true;error.value=''
  try{const current=await readCurrent();visible.value=false;const library=await previewRef.value.confirm();if(library)await persist(context.value,context.value.node.prices,true,library.version)}
  catch(e){error.value=getLocalizedErrorMessage(e,e.message||'同步客户参考价失败');visible.value=true}
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
