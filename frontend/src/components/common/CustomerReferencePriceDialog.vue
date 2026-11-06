<template>
  <DraggableFormDialog v-model="visible" title="客户笔译报价 · 选择参考价" append-to-body width="min(1120px, calc(100vw - 32px))" top="5vh" class="reference-price-picker" :close-on-click-modal="false" :before-close="cancel">
    <div v-loading="loading">
      <p>{{library?.client?.name||clientName||'当前客户'}} · 只可采用语种方向、计量单位、币种及单价对应数量全部匹配的报价。</p>
      <CustomerTranslationRates :client-id="clientId" :can-write="canWrite" button-label="查看／编辑客户笔译报价" @saved="librarySaved" />
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-alert v-else-if="!rows.some(row=>row.match.matched)" title="暂无完整匹配的报价，可查看并编辑客户报价，或先明确项目计量单位。" type="warning" :closable="false" />
      <el-table :data="rows" border max-height="400" row-key="id">
        <el-table-column label="选择" width="65"><template #default="{row}"><el-radio v-model="selected" :value="row.id" :disabled="!row.match.matched" :aria-label="`选用报价 ${row.languagePair} ${unitLabel(row)}`"><span /></el-radio></template></el-table-column>
        <el-table-column prop="languagePair" label="语种方向" min-width="140" />
        <el-table-column label="计量单位" min-width="110"><template #default="{row}">{{unitLabel(row)}}</template></el-table-column>
        <el-table-column prop="currency" label="币种" width="70" /><el-table-column prop="unitSize" label="单价对应数量" width="115" />
        <el-table-column label="报价" min-width="190"><template #default="{row}">{{taxPriceSummary(row.taxPrices,row.currency,row.unitSize+'单位',false)||row.amount}}</template></el-table-column>
        <el-table-column label="匹配情况" min-width="230"><template #default="{row}"><el-tag :type="row.match.matched?'success':'warning'">{{row.match.matched?'完整匹配':'不匹配'}}</el-tag><small>{{row.match.reasons.join('；')}}</small></template></el-table-column>
      </el-table>
    </div>
    <template #footer><el-button @click="cancel()">取消</el-button><el-button type="primary" :disabled="loading||!!error||!selected" @click="accept">采用所选报价</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref,onBeforeUnmount} from 'vue'
import {getCustomerTranslationRates} from '@/api/translationCustomerFinance'
import {priceMatch,pricingUnit,expectedOrderPrices} from '@/utils/customerRateMatching'
import {metricName} from '@/utils/translationQuantityBasis'
import {taxPriceSummary} from '@/utils/taxPrices'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
const props=defineProps({clientId:String,clientName:String,prices:Array,matrix:Object,languagePair:String,refreshProject:Function})
const emit=defineEmits(['library-saved'])
const visible=ref(false),loading=ref(false),library=ref(null),error=ref(''),selected=ref('')
const canWrite=hasPermission('clients:write')
let resolver,sequence=0
const unitLabel=row=>{const unit=pricingUnit(row.metric,null,true);return unit?metricName(unit):'未明确单位'}
const rows=computed(()=>{const expected=expectedOrderPrices(props.prices,props.languagePair,props.matrix);return (library.value?.items||[]).map(row=>{const matches=expected.map(price=>priceMatch(row,price,props.matrix));const match=matches.find(item=>item.matched)||matches.sort((a,b)=>a.reasons.length-b.reasons.length)[0]||{matched:false,reasons:['项目尚未设置语种或单价']};return {...row,match}})})
function settle(value){resolver?.(value);resolver=undefined}
function cancel(done){sequence++;visible.value=false;settle(null);if(typeof done==='function')done()}
async function load(){const current=++sequence;loading.value=true;error.value='';selected.value='';try{const data=await getCustomerTranslationRates(props.clientId);if(current!==sequence)return;library.value=data;if(!data.ready)error.value='客户报价存储尚未初始化';const matching=rows.value.filter(row=>row.match.matched);if(matching.length===1)selected.value=matching[0].id}catch(e){if(current===sequence)error.value=getLocalizedErrorMessage(e,'客户报价加载失败')}finally{if(current===sequence)loading.value=false}}
function confirm(){settle(null);library.value=null;visible.value=true;const result=new Promise(resolve=>resolver=resolve);void load();return result}
function accept(){const row=rows.value.find(item=>item.id===selected.value&&item.match.matched);if(!row)return;visible.value=false;settle({price:row,version:library.value.version})}
async function librarySaved(){loading.value=true;try{await props.refreshProject?.();await load();emit('library-saved')}catch(e){error.value=getLocalizedErrorMessage(e,'项目价格刷新失败');loading.value=false}}
onBeforeUnmount(()=>{sequence++;settle(null)})
defineExpose({confirm})
</script>
<style scoped>
p,small{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}small{display:block}.customer-reference-rates{margin-bottom:12px}.el-alert{margin:12px 0}:global(.reference-price-picker){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.reference-price-picker>.el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.reference-price-picker>.el-dialog__header),:global(.reference-price-picker>.el-dialog__footer){flex:none}
</style>
