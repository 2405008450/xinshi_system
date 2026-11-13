<template>
  <section class="payment-confirmation" data-dialog-field-search-group data-dialog-field-search-group-title="付款情况">
    <div class="payment-confirmation-heading"><strong>付款情况</strong><div><slot name="actions" /><el-button v-if="projectId" link @click="openHistory">付款修改记录</el-button></div></div>
    <p v-if="summaryLabel" class="payment-confirmation-help">请按上方{{summaryLabel}}的计费合计付款，登记全款或尾款时按同一金额核对。</p>
    <el-form-item label="付款状态" :prop="`${prefix}.paymentOption`" :rules="value.isPaid?[{required:true,message:'请选择付款状态',trigger:'change'}]:[]">
      <div class="payment-status-controls">
        <el-radio-group :disabled="switching" :model-value="value.isPaid?value.paymentOption:null" @update:model-value="selectStatus"><el-radio v-for="item in paymentOptions" :key="item.value" :value="item.value">{{item.label}}</el-radio></el-radio-group>
        <el-button size="small" :disabled="!value.isPaid||switching" aria-label="取消已付定金或已付全款" title="清除付款状态和明细，保存后生效；保留历史记录" @click="clearStatus">清除选择</el-button>
      </div>
      <small v-if="value.paymentOption==='once'">历史：已登记分次付款</small>
    </el-form-item>
    <FullPaymentMatchFields v-if="value.isPaid&&(value.paymentOption==='full'||value.fullPaymentSource==='details')" :draft-totals="draftTotals" :summary-label="summaryLabel" :pricing-mode="pricingMode" :billing-tax-mode="billingTaxMode" :from-details="value.paymentOption!=='full'" @reference-change="emit('reference-change',$event)" :model-value="value" :project-id="projectId" :prefix="prefix" @update:model-value="emit('update:modelValue',$event)" />
    <el-form-item v-if="value.isPaid&&!detailsInPayments" label="付款账户" :prop="`${prefix}.paymentAccount`"><PaymentAccountSelect :model-value="value.paymentAccount" @update:model-value="update('paymentAccount',$event)" /></el-form-item>
    <el-row v-if="value.isPaid && value.paymentOption==='full'" :gutter="12">
      <el-col :xs="24" :md="12"><el-form-item label="确认人"><ReadonlyField :model-value="value.fullPaymentConfirmedByName || ''" source="auto" placeholder="待行政部确认" /></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="确认时间"><ReadonlyField :model-value="value.fullPaymentConfirmedAt ? formatDateTime(value.fullPaymentConfirmedAt) : ''" source="auto" placeholder="待行政部确认" /></el-form-item></el-col>
    </el-row>
    <slot v-if="value.isPaid && value.paymentOption==='full'" name="confirm-full" />
    <el-form-item v-if="value.isPaid&&!detailsInPayments" label="支付截图及备注"><ScreenshotInput :model-value="value.proofs" type="textarea" :rows="2" :maxlength="20000" placeholder="可粘贴、拖入或上传支付截图，填写付款备注" @update:model-value="update('proofs',$event)" /></el-form-item>
    <p v-if="value.isPaid&&!detailsInPayments" class="payment-confirmation-help">支付截图长期保存；清除选择后可在付款修改记录中查看原有凭证。</p>
    <DraggableFormDialog v-model="historyVisible" title="付款修改记录" width="min(860px, calc(100vw - 32px))" top="5vh" append-to-body class="payment-confirmation-history">
      <div v-loading="historyLoading"><el-alert v-if="historyError" :title="historyError" type="error" :closable="false" /><el-empty v-else-if="!historyItems.length" description="暂无修改记录" /><div v-for="item in historyItems" :key="item.id" class="confirmation-history-item"><p>{{item.after.action||'修改付款情况'}} · {{formatDateTime(item.created_at)}} · {{item.actor_name}}</p><el-descriptions :column="1" border><el-descriptions-item label="修改前">{{paymentConfirmationLabel(item.before)}}<ScreenshotText :text="item.before.proofs" /><PaymentDetailsHistoryTable :payments="item.before.payment_details||[]" /></el-descriptions-item><el-descriptions-item label="修改后">{{paymentConfirmationLabel(item.after)}}<ScreenshotText :text="item.after.proofs" /><PaymentDetailsHistoryTable :payments="item.after.payment_details||[]" /></el-descriptions-item></el-descriptions></div><el-pagination v-model:current-page="historyPage" :page-size="10" :total="historyTotal" layout="prev, pager, next" @current-change="loadHistory" /></div>
      <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {computed,ref} from 'vue'
import api from '@/api'
import {ElMessageBox,ElMessage} from 'element-plus'
import {formatBusinessDateTime as formatDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {paymentOptions,paymentConfirmationForm,paymentConfirmationLabel,clearPaymentSelection,switchPaymentSelection} from '@/utils/paymentConfirmation'
import ScreenshotInput from './ScreenshotInput.vue'
import PaymentAccountSelect from './PaymentAccountSelect.vue'
import ReadonlyField from './ReadonlyField.vue'
import FullPaymentMatchFields from './FullPaymentMatchFields.vue'
import ScreenshotText from './ScreenshotText.vue'
import PaymentDetailsHistoryTable from './PaymentDetailsHistoryTable.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
const props=defineProps({modelValue:Object,projectId:{type:String,default:''},prefix:{type:String,default:'confirmation'},detailsInPayments:Boolean,pricingMode:String,billingTaxMode:String,payments:{type:Array,default:null},draftTotals:{type:Array,default:null},summaryLabel:String})
const emit=defineEmits(['update:modelValue','reference-change'])
const value=computed(()=>paymentConfirmationForm(props.modelValue))
function update(key,data){emit('update:modelValue',{...value.value,[key]:data})}
const switching=ref(false)
async function selectStatus(option){
  if(switching.value)return
  switching.value=true
  try{
    const payments=props.payments??(props.projectId&&!value.value.clearDetails?(await api.get(`/translation-payments/${props.projectId}`)).payments:[])??[]
    const next=await switchPaymentSelection(value.value,option,{payments,confirm:message=>ElMessageBox.confirm(message,'切换付款状态',{type:'warning',confirmButtonText:'继续并清除',cancelButtonText:'取消',closeOnClickModal:false})})
    if(next)emit('update:modelValue',next)
  }catch(e){ElMessage.error(getLocalizedErrorMessage(e,'读取付款数据失败，未切换付款状态'))}
  finally{switching.value=false}
}
function clearStatus(){emit('update:modelValue',clearPaymentSelection(value.value))}
const historyVisible=ref(false),historyLoading=ref(false),historyError=ref(''),historyItems=ref([]),historyPage=ref(1),historyTotal=ref(0)
async function loadHistory(){historyLoading.value=true;historyError.value='';try{const data=await api.get(`/translation-payments/${props.projectId}/confirmation-history`,{params:{page:historyPage.value}});historyItems.value=data.items;historyTotal.value=data.total}catch(e){historyError.value=getLocalizedErrorMessage(e,'付款修改记录加载失败')}finally{historyLoading.value=false}}
function openHistory(){historyPage.value=1;historyItems.value=[];historyVisible.value=true;void loadHistory()}
</script>
<style scoped>.payment-status-controls{display:flex;align-items:center;gap:20px;flex-wrap:wrap;min-width:0}.payment-status-controls>.el-button{flex:none;margin-left:0}.payment-confirmation{margin:16px 0;padding:16px;border:1px solid var(--el-border-color);border-radius:8px}.payment-confirmation-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}.payment-confirmation-heading>div{display:flex;gap:12px;flex-wrap:wrap}.payment-confirmation-help{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6;margin:0}.confirmation-history-item{margin-bottom:14px}:global(.payment-confirmation-history){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.payment-confirmation-history>.el-dialog__body){min-height:0;overflow:auto;flex:1}:global(.payment-confirmation-history>.el-dialog__header),:global(.payment-confirmation-history>.el-dialog__footer){flex:none}</style>
