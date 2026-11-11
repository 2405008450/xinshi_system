<template>
<section class="payment-registration-fields">
        <el-descriptions v-if="depositSelected" :column="3" border class="payment-summary"><el-descriptions-item label="预定合计">{{total('planned_amount')}}</el-descriptions-item><el-descriptions-item label="实际付款合计">{{total('actual_amount')}}</el-descriptions-item><el-descriptions-item label="付款状态">{{paymentStatus}}</el-descriptions-item></el-descriptions>
        <PaymentConfirmationFields :pricing-mode="form.pricingMode" :billing-tax-mode="effectiveBillingTaxMode(form)" :draft-totals="draftTotals" :model-value="confirmation" :project-id="projectId" :details-in-payments="depositSelected" :payments="payments" :prefix="prefix" @update:model-value="updateConfirmation"><template #actions><slot name="actions" /></template></PaymentConfirmationFields>
        <p v-if="isFull" class="payment-help">已确认全款，无需填写分期明细；切换时确认清除的明细会记入历史。</p>
        <template v-if="depositSelected">
        <div v-for="(item,index) in payments" :key="item.id||index" class="project-payment-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`付款明细 ${index+1}`">
          <div class="payment-row-heading"><strong>付款明细 {{index+1}}</strong><el-button link type="danger" @click="removePayment(index)">移除</el-button></div>
          <el-row :gutter="12"><el-col :xs="12" :md="6"><el-form-item label="阶段"><ReadonlyField v-if="index===0&&depositSelected" model-value="定金" source="auto" /><el-select v-else v-model="item.stage_type" @change="syncFromDetails"><el-option label="定金" value="deposit" /><el-option label="中期款" value="mid" /><el-option label="尾款" value="final" /></el-select></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="期次" :prop="`paymentDraft.${index}.stage_no`" :rules="[{required:true,type:'number',min:1,max:999,message:'请输入1至999的期次',trigger:'change'},{validator:(_rule,_value,callback)=>validateStage(index,callback),trigger:'change'}]"><el-input-number v-model="item.stage_no" :min="1" :max="999" :precision="0" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="预定金额"><el-input-number v-model="item.planned_amount" :min="0" :precision="2" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="实际金额" :prop="`paymentDraft.${index}.actual_amount`" :rules="hasFinal?[{required:true,type:'number',message:'登记尾款后请填写每次实际金额',trigger:'change'}]:[]"><el-input-number v-model="item.actual_amount" @change="syncFromDetails" :min="0" :precision="2" :controls="false" /></el-form-item></el-col></el-row>
          <el-row :gutter="12"><el-col :xs="24" :md="12"><el-form-item label="付款时间"><el-date-picker v-model="item.payment_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" clearable /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="付款方式"><PaymentAccountSelect v-model="item.payment_method" @update:model-value="syncFromDetails" /></el-form-item></el-col></el-row>
          <el-form-item label="支付截图及备注"><ScreenshotInput v-model="item.proofs" type="textarea" :rows="2" :maxlength="20000" placeholder="可粘贴、拖入或上传本次付款截图，填写付款备注" /></el-form-item><p class="payment-help">每条明细的截图及备注独立保存；修改或移除后可在付款修改记录中追溯。</p>
        </div>
        <el-button :disabled="payments.length>=100" @click="addPayment">新增付款明细</el-button>
        </template>

</section>
</template>

<script setup>
import {computed,watch} from 'vue'
import {effectiveBillingTaxMode} from '@/utils/billingTaxMode'
import PaymentConfirmationFields from './PaymentConfirmationFields.vue'
import ReadonlyField from './ReadonlyField.vue'
import PaymentAccountSelect from './PaymentAccountSelect.vue'
import ScreenshotInput from './ScreenshotInput.vue'
import {paymentConfirmationForm,fixFirstDepositStage,clearPaymentSelection} from '@/utils/paymentConfirmation'
const form=defineModel({type:Object,required:true})
defineProps({projectId:String,draftTotals:{type:Array,default:null},prefix:{type:String,default:'paymentConfirmation'}})
const confirmation=computed({get:()=>form.value.paymentConfirmation,set:value=>{form.value.paymentConfirmation=value}})
const payments=computed({get:()=>form.value.paymentDraft||[],set:value=>{form.value.paymentDraft=value}})
const depositSelected=computed(()=>confirmation.value?.isPaid&&confirmation.value.paymentOption==='deposit')
const isFull=computed(()=>confirmation.value?.isPaid&&confirmation.value.paymentOption==='full')
const hasFinal=computed(()=>depositSelected.value&&payments.value.some(item=>item.stage_type==='final'))
const cents=value=>BigInt(Number(value||0).toFixed(2).replace('.',''))
const totalCents=key=>payments.value.reduce((sum,item)=>sum+cents(item[key]),0n)
const total=key=>{const value=totalCents(key);return `${value/100n}.${String(value%100n).padStart(2,'0')}`}
const paymentStatus=computed(()=>hasFinal.value?'尾款核对（累计实付）':totalCents('actual_amount')>0n?'已付定金／部分付款':'已确认定金（待补充明细）')
function addPayment(){if(!depositSelected.value||payments.value.length>=100)return;const stage=payments.value.length?'mid':'deposit';payments.value=[...payments.value,{stage_type:stage,stage_no:Math.max(0,...payments.value.filter(item=>item.stage_type===stage).map(item=>item.stage_no))+1,planned_amount:undefined,actual_amount:undefined,payment_time:null,payment_method:confirmation.value.paymentAccount||'',proofs:payments.value.length?'':confirmation.value.proofs||''}]}
function ensureFirstDeposit(){if(!depositSelected.value)return;if(!payments.value.length)addPayment();fixFirstDepositStage(confirmation.value,payments.value);if(!payments.value[0].payment_method)payments.value[0].payment_method=confirmation.value.paymentAccount||''}
function updateConfirmation(value){
  if(value.replaceDetails&&(!confirmation.value.replaceDetails||value.paymentOption!==confirmation.value.paymentOption))payments.value=[]
  confirmation.value=paymentConfirmationForm(value)
  if(!confirmation.value.isPaid){payments.value=[];confirmation.value=clearPaymentSelection(confirmation.value);return}
  ensureFirstDeposit()
  if(hasFinal.value)syncFromDetails()
  for(const item of payments.value)if(!item.payment_method)item.payment_method=confirmation.value.paymentAccount||''
}
function syncFromDetails(){
  if(isFull.value)return
  const actual=payments.value.filter(item=>Number(item.actual_amount||0)>0)
  const methods=[...new Set(actual.map(item=>item.payment_method).filter(Boolean))]
  confirmation.value={...confirmation.value,paymentAccount:methods.length===1?methods[0]:methods.length>1?'':confirmation.value.paymentAccount,fullPaymentSource:hasFinal.value?'details':null,fullPaymentAmount:hasFinal.value&&payments.value.every(item=>item.actual_amount!=null)?Number(total('actual_amount')):null,fullMatchStatus:'pending'}
}
function removePayment(index){payments.value=payments.value.filter((_item,i)=>i!==index);ensureFirstDeposit();syncFromDetails()}
function validateStage(index,callback){const item=payments.value[index];const duplicate=payments.value.some((row,i)=>i!==index&&row.stage_type===item.stage_type&&row.stage_no===item.stage_no);callback(duplicate?new Error('同一付款阶段的期次不能重复'):undefined)}
watch(()=>form.value.paymentConfirmation,ensureFirstDeposit,{immediate:true})
</script>
<style scoped>
.project-payment-row{padding:14px;border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.payment-row-heading{display:flex;justify-content:space-between;margin-bottom:10px}.project-payment-row .el-input-number{width:100%}.payment-summary{margin:16px 0}.payment-help{font-size:12px;color:var(--el-text-color-secondary)}
</style>
