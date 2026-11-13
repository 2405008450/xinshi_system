<template>
  <DraggableFormDialog v-model="visible" append-to-body title="比较客户参考价并确认同步" class="customer-rate-sync-preview" width="min(1100px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="cancel">
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-descriptions :column="2" border size="small"><el-descriptions-item label="客户全称">{{library?.client?.name||clientName||'-'}}</el-descriptions-item><el-descriptions-item label="客户编号">{{library?.client?.code||'-'}}</el-descriptions-item><el-descriptions-item label="客户简称" :span="2">{{library?.client?.shortName||clientName||'-'}}</el-descriptions-item></el-descriptions>
      <CustomerTranslationRates :client-id="clientId" :can-write="canWriteClients" button-label="查看／编辑客户笔译报价" @saved="reloadLibrary" />
      <p v-if="unmatchedPrice">本次填写的单价在客户管理中没有匹配报价。是否保存项目并同步客户报价？</p>
      <p v-else>请核对语种方向、单价、货币和计价单位。确认后保存项目并同步参考价。</p>
      <el-table :data="comparisons" border max-height="400">
        <el-table-column prop="direction" label="语种方向" min-width="160" />
        <el-table-column label="客户信息现有参考价" min-width="270"><template #default="{row}"><div v-if="!row.current.length" class="missing-rate">尚无该语种方向的参考价</div><div v-for="price in row.current" :key="price.id" class="price-line">{{describe(price)}}<small v-if="price.updatedAt">更新时间：{{formatTime(price.updatedAt)}}</small></div></template></el-table-column>
        <el-table-column label="本次项目单价" min-width="250"><template #default="{row}">{{describe(row.price)}}</template></el-table-column>
        <el-table-column prop="result" label="比较结果／同步后" min-width="220" />
      </el-table>
      <h4>客户管理中的全部笔译报价</h4>
      <el-table :data="library?.items||[]" border max-height="240" empty-text="客户暂无笔译报价">
        <el-table-column prop="languagePair" label="语种方向" min-width="160" />
        <el-table-column label="单价" min-width="250"><template #default="{row}">{{describe(row)}}</template></el-table-column>
        <el-table-column label="统计口径" min-width="140"><template #default="{row}">{{basisLabel(row.metric)}}</template></el-table-column>
      </el-table>
      <p>本次未包含的客户参考价予以保留。客户参考价变更会自动同步至仍沿用原价的项目，项目单独调整过的单价保留。</p>
    </div>
    <template #footer><el-button @click="cancel()">取消</el-button><el-button type="primary" :disabled="loading||!!error||!comparisons.length||invalidUnits" @click="accept">确认保存并同步</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,computed,onBeforeUnmount} from 'vue'
import {getCustomerTranslationRates} from '@/api/translationCustomerFinance'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import {hasPermission} from '@/utils/permission'
import {priceMatch,pricingUnit,sameCustomerRatePrice} from '@/utils/customerRateMatching'
import {taxPriceSummary} from '@/utils/taxPrices'
import {metricName} from '@/utils/translationQuantityBasis'
import {basisLabel} from '@/utils/translationQuantityBasis'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:String,clientName:String,prices:{type:Array,default:()=>[]},matrix:Object,refreshProject:Function})
const canWriteClients=hasPermission('clients:write')
const visible=ref(false),loading=ref(false),error=ref(''),library=ref(null),unmatchedPrice=ref(false)
const invalidUnits=computed(()=>props.prices.some(price=>!pricingUnit(price.metric,props.matrix)))
let resolver,sequence=0
function describe(price){
  const currency=price.currency||'CNY'
  const unit=`${price.unitSize||1} ${metricName(pricingUnit(price.metric,props.matrix))}`
  return taxPriceSummary(price.taxPrices,currency,unit,false).replaceAll('\n',' · ')||`${currency} ${price.amount} / ${unit}`
}
const comparisons=computed(()=>props.prices.map(price=>{
  const current=(library.value?.items||[]).filter(item=>item.languagePair===price.languagePair)
  const matching=current.find(item=>priceMatch(item,price,props.matrix).matched)
  const result=!pricingUnit(price.metric,props.matrix)?'项目计量单位未明确，请先补录或选择统计口径':!current.length?'无对应语种方向，将新增参考价':!matching?'语种、单位、币种或计价数量不匹配，将新增报价':sameCustomerRatePrice(matching,price)?'全部匹配，单价一致':'计价条件全部匹配，单价不同，将更新该报价'
  return {direction:price.languagePair,current,price,result}
}))
function settle(value){resolver?.(value);resolver=undefined}
function cancel(done){sequence++;loading.value=false;visible.value=false;settle(null);if(typeof done==='function')done()}
function accept(){if(loading.value||error.value)return;visible.value=false;settle(library.value)}
async function reloadLibrary(){const current=++sequence;loading.value=true;error.value='';try{await props.refreshProject?.();const data=await getCustomerTranslationRates(props.clientId);if(current===sequence)library.value=data}catch(e){if(current===sequence)error.value=getLocalizedErrorMessage(e,'客户报价加载失败')}finally{if(current===sequence)loading.value=false}}
function confirm(initialLibrary=null){
  settle(null);const current=++sequence;visible.value=true;loading.value=!initialLibrary;error.value='';library.value=initialLibrary
  unmatchedPrice.value=!!initialLibrary
  const result=new Promise(resolve=>{resolver=resolve})
  if(initialLibrary)return result
  getCustomerTranslationRates(props.clientId).then(data=>{if(current!==sequence)return;library.value=data;if(!data.ready)error.value='客户参考价存储尚未初始化'}).catch(e=>{if(current===sequence)error.value=getLocalizedErrorMessage(e,'客户参考价加载失败')}).finally(()=>{if(current===sequence)loading.value=false})
  return result
}
onBeforeUnmount(()=>{sequence++;settle(null)})
defineExpose({confirm,cancel})
</script>
<style scoped>
.price-line{margin-bottom:8px}small{display:block;color:#64748b}.missing-rate{color:#b45309}p{font-size:12px;color:#64748b}
:global(.customer-rate-sync-preview){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.customer-rate-sync-preview .el-dialog__header),:global(.customer-rate-sync-preview .el-dialog__footer){flex-shrink:0}
:global(.customer-rate-sync-preview .el-dialog__body){flex:1;min-height:0;overflow-y:auto}
</style>
