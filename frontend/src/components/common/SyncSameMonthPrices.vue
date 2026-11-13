<template>
  <div>
    <div class="price-sync-scopes">
      <el-button :disabled="disabled || loading || !month || !clientId" @click="open('same_month')">{{compact?'同步同月订单':'同步到同客户同月同语种同单位订单…'}}</el-button>
      <el-button :disabled="disabled || loading || !projectId || !orderId" @click="open('project_children')">同步到本订单同语种同单位的各级子订单…</el-button>
      <small v-if="syncCount" class="sync-count">已同步 {{syncCount}} 次</small>
    </div>
    <DraggableFormDialog v-model="visible" append-to-body class="same-month-price-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" :title="childScope ? '确认同步本订单各级子订单单价' : '确认同步同客户同月同语种单价'" :close-on-click-modal="false" :before-close="close">
      <div v-loading="loading">
        <CustomerTranslationRates v-if="clientId" :client-id="clientId" :can-write="canWriteClients" button-label="查看／编辑客户笔译报价" @saved="open(scope)" />
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <p>{{`将${sourceOrder}的单价同步至${destination}。匹配 ${preview?.targets?.length || 0} 个订单。`}}</p>
        <p>语种方向、实际计量单位、币种和单价对应数量均匹配才会同步。各订单的工作量、调整金额和说明保留。</p>
        <el-table :data="preview?.targets||[]" border max-height="400"><el-table-column prop="orderNo" label="订单号" min-width="180" /><el-table-column prop="projectName" label="项目名称" min-width="180" /><el-table-column prop="languagePair" label="语种方向" min-width="160" /><el-table-column label="当前单价" min-width="220"><template #default="{row}"><p v-for="price in row.before" :key="price.id">{{text(price)}}</p></template></el-table-column><el-table-column label="将同步为" min-width="220"><template #default="{row}"><p v-for="(price,index) in row.prices" :key="index">{{text(price)}}</p></template></el-table-column></el-table>
        <el-alert v-if="preview?.skipped?.length" type="warning" :closable="false" :title="`${preview.skipped.length} 个订单不匹配，已跳过`" /><p v-for="item in preview?.skipped||[]" :key="item.orderNo">{{item.orderNo}}：{{item.reason}}</p>
      </div><template #footer><el-button :disabled="saving" @click="close()">取消</el-button><el-button type="primary" :disabled="loading||!!error||!preview?.targets?.length" :loading="saving" @click="apply">确认同步 {{preview?.targets?.length||0}} 个订单</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import {hasPermission} from '@/utils/permission'
import {ElMessage} from 'element-plus'
import {previewSameMonthPrices,applySameMonthPrices,getSameMonthPriceSyncStatus} from '@/api/translationCustomerFinance'
import {basisLabel} from '@/utils/translationQuantityBasis'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({projectId:String,orderId:String,sourceOrderNo:String,version:String,month:String,clientId:String,disabled:Boolean,prepare:Function,compact:Boolean})
const emit=defineEmits(['synced'])
const canWriteClients=hasPermission('clients:write')
const visible=ref(false),loading=ref(false),saving=ref(false),preview=ref(null),error=ref('')
const scope=ref('same_month')
const childScope=computed(()=>scope.value==='project_children')
const sourceOrder=computed(()=>props.sourceOrderNo ? `订单 ${props.sourceOrderNo}` : '当前订单')
const destination=computed(()=>childScope.value
  ? '该订单下匹配的各级子订单'
  : `${preview.value?.clientName || '同一客户'}在 ${preview.value?.billingMonth || props.month} 账单月份内匹配的订单`)
const syncCount=ref(0)
let statusSequence=0
watch(()=>[props.projectId,props.orderId],async()=>{const current=++statusSequence;syncCount.value=0;if(!props.projectId||!props.orderId)return;try{const data=await getSameMonthPriceSyncStatus(props.projectId,props.orderId);if(current===statusSequence)syncCount.value=data.syncCount||0}catch{}},{immediate:true})
onBeforeUnmount(()=>{statusSequence++})
let request
const text=price=>`${price.languagePair} · ${price.currency} ${price.amount} / ${price.unitSize} · ${basisLabel(price.metric)}`
async function open(nextScope){
  if(props.disabled||loading.value||saving.value)return
  loading.value=true
  try{
    const prepared=props.prepare?await props.prepare():null
    if(prepared===false)return
    scope.value=nextScope
    request={...(prepared||{order_id:props.orderId,version:props.version,billing_month:props.month}),scope:nextScope}
    if(childScope.value)delete request.billing_month
    preview.value=null;error.value='';visible.value=true
    preview.value=await previewSameMonthPrices(props.projectId,request)
  }catch(e){error.value=getLocalizedErrorMessage(e,'匹配订单预览失败');visible.value=true}
  finally{loading.value=false}
}
function close(done){if(saving.value||loading.value)return;if(typeof done==='function')done();else visible.value=false}
async function apply(){
  if(saving.value||loading.value||!preview.value?.token)return
  saving.value=true
  error.value=''
  try{
    const data=await applySameMonthPrices(props.projectId,{...request,token:preview.value.token})
    syncCount.value=data.syncCount||syncCount.value+1
    ElMessage.success(`已将${sourceOrder.value}的单价同步至${destination.value}，共 ${data.updatedOrders} 个`)
    visible.value=false
    window.dispatchEvent(new CustomEvent('translation-finance-changed',{detail:childScope.value?{projectId:props.projectId}:{clientId:props.clientId}}))
    emit('synced')
  }catch(e){error.value=getLocalizedErrorMessage(e,'同步失败，请重新预览')}
  finally{saving.value=false}
}
</script>
<style scoped>
.price-sync-scopes{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.price-sync-scopes :deep(.el-button){margin-left:0;max-width:100%;height:auto;min-height:32px;white-space:normal;text-align:left}
.sync-count{display:inline-block;margin:0 0 0 6px;padding:0 5px;border-radius:8px;background:var(--el-color-success-light-8);color:var(--el-color-success);font-size:11px;line-height:18px}
small{display:block;font-size:12px;color:#64748b;margin-top:6px}:global(.same-month-price-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.same-month-price-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.same-month-price-dialog .el-dialog__header),:global(.same-month-price-dialog .el-dialog__footer){flex-shrink:0}:global(.same-month-price-dialog .el-dialog__footer){border-top:1px solid #dbe3ec;background:#f8fafc}
</style>
