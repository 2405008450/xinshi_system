<template>
  <div><el-button :disabled="disabled||!month||!clientId" @click="open">同步到同客户同月同语种同单位订单…</el-button><small v-if="disabled">有未保存修改，请先保存当前单价后再同步。</small>
    <DraggableFormDialog v-model="visible" append-to-body class="same-month-price-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" title="确认同步同客户同月同语种单价" :close-on-click-modal="false" :before-close="close">
      <div v-loading="loading"><CustomerTranslationRates :client-id="clientId" :can-write="canWriteClients" button-label="查看／编辑客户笔译报价" @saved="open" /><el-alert v-if="error" :title="error" type="error" :closable="false" /><p>客户：{{preview?.clientName||'-'}}；账单月份：{{preview?.billingMonth||month}}；匹配 {{preview?.targets?.length||0}} 个订单。</p><p>只同步语种方向、计量单位、币种及单价对应数量全部匹配的单价，保留各订单的数量、调价和说明；未独立登记月份的下级按上级月份匹配。无可确定账单月份的订单不参与。</p>
        <el-table :data="preview?.targets||[]" border max-height="400"><el-table-column prop="orderNo" label="订单号" min-width="180" /><el-table-column prop="projectName" label="项目名称" min-width="180" /><el-table-column prop="languagePair" label="语种方向" min-width="160" /><el-table-column label="当前单价" min-width="220"><template #default="{row}"><p v-for="price in row.before" :key="price.id">{{text(price)}}</p></template></el-table-column><el-table-column label="将同步为" min-width="220"><template #default="{row}"><p v-for="(price,index) in row.prices" :key="index">{{text(price)}}</p></template></el-table-column></el-table>
        <el-alert v-if="preview?.skipped?.length" type="warning" :closable="false" :title="`${preview.skipped.length} 个订单不匹配，已跳过`" /><p v-for="item in preview?.skipped||[]" :key="item.orderNo">{{item.orderNo}}：{{item.reason}}</p>
      </div><template #footer><el-button :disabled="saving" @click="close()">取消</el-button><el-button type="primary" :disabled="loading||!!error||!preview?.targets?.length" :loading="saving" @click="apply">确认同步 {{preview?.targets?.length||0}} 个订单</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {ref} from 'vue'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import {hasPermission} from '@/utils/permission'
import {ElMessage} from 'element-plus'
import {previewSameMonthPrices,applySameMonthPrices} from '@/api/translationCustomerFinance'
import {basisLabel} from '@/utils/translationQuantityBasis'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({projectId:String,orderId:String,version:String,month:String,clientId:String,disabled:Boolean,prepare:Function})
const emit=defineEmits(['synced'])
const canWriteClients=hasPermission('clients:write')
const visible=ref(false),loading=ref(false),saving=ref(false),preview=ref(null),error=ref('')
let request
const text=price=>`${price.languagePair} · ${price.currency} ${price.amount} / ${price.unitSize} · ${basisLabel(price.metric)}`
async function open(){if(props.disabled)return;const prepared=props.prepare?await props.prepare():null;if(prepared===false)return;request=prepared||{order_id:props.orderId,version:props.version,billing_month:props.month};preview.value=null;error.value='';visible.value=true;loading.value=true;try{preview.value=await previewSameMonthPrices(props.projectId,request)}catch(e){error.value=getLocalizedErrorMessage(e,'匹配订单预览失败')}finally{loading.value=false}}
function close(done){if(saving.value||loading.value)return;if(typeof done==='function')done();else visible.value=false}
async function apply(){if(saving.value||!preview.value?.token)return;saving.value=true;error.value='';try{const data=await applySameMonthPrices(props.projectId,{...request,token:preview.value.token});visible.value=false;ElMessage.success(`已同步 ${data.updatedOrders} 个订单单价，并保留修改记录`);emit('synced')}catch(e){error.value=getLocalizedErrorMessage(e,'同步失败，请重新预览')}finally{saving.value=false}}
</script>
<style scoped>
small{display:block;font-size:12px;color:#64748b;margin-top:6px}:global(.same-month-price-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.same-month-price-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.same-month-price-dialog .el-dialog__header),:global(.same-month-price-dialog .el-dialog__footer){flex-shrink:0}:global(.same-month-price-dialog .el-dialog__footer){border-top:1px solid #dbe3ec;background:#f8fafc}
</style>
