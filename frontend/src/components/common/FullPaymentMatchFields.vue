<template>
  <div class="full-payment-match" v-loading="loading">
    <div class="full-payment-inputs">
      <el-form-item :label="fromDetails?'累计实付金额':'已付全款金额'" :prop="`${prefix}.fullPaymentAmount`" :rules="[{validator:validateAmount,trigger:'change'}]"><ReadonlyField v-if="fromDetails" :model-value="value.fullPaymentAmount==null?'待填写各次实际金额':value.fullPaymentAmount.toFixed(2)" source="auto" /><el-input-number v-else :model-value="value.fullPaymentAmount??undefined" :min="0" :precision="2" :controls="false" aria-label="已付全款金额" @focus="editingAmount=true" @blur="editingAmount=false" @update:model-value="update('fullPaymentAmount',$event??null)" /></el-form-item>
      <el-form-item label="付款币种"><el-select :model-value="value.fullPaymentCurrency" aria-label="付款币种" @update:model-value="update('fullPaymentCurrency',$event)"><el-option v-for="currency in currencies" :key="currency" :value="currency" /></el-select></el-form-item>
      <el-form-item :label="referenceFieldLabel"><div class="full-payment-reference"><ReadonlyField :model-value="reference?`${reference.currency} ${reference.amount}`:'暂无可匹配总价'" source="auto" :aria-label="referenceFieldLabel" /><span v-if="reference&&!fixedCharge" class="full-payment-tax-mode">{{referenceTaxLabel}}</span></div><p v-if="fixedCharge" class="full-payment-hint full-payment-reference-hint">请在上面计费口径调整含税/不含税固定收费。</p></el-form-item>
    </div>
    <div class="full-payment-result-row">
    <p class="full-payment-result"><el-tag :type="status==='matched'?'success':status==='mismatch'?'danger':'info'">{{status==='matched'?'已匹配':status==='mismatch'?'不匹配':'待核对'}}</el-tag><span v-if="reference">{{fixedCharge?referenceFieldLabel:reference.label}}：{{reference.currency}} {{reference.amount}}</span><span v-else>项目暂无可匹配总价</span></p>
    <el-form-item v-if="status==='mismatch'" ref="reasonField" class="full-payment-reason" label-position="left" data-screenshot-editor="own" label="不匹配原因" :prop="`${prefix}.mismatchReason`" :rules="[{required:true,whitespace:true,message:'请说明全款金额不匹配的原因',trigger:'blur'}]"><el-input :model-value="value.mismatchReason" type="textarea" :autosize="{minRows:1,maxRows:3}" maxlength="2000" show-word-limit aria-label="不匹配原因" @update:model-value="update('mismatchReason',$event)" /></el-form-item>
    </div>
    <p v-if="legacy" class="full-payment-hint">历史全款确认未登记金额，补充金额后可核对项目总价。</p>
    <p v-if="error" class="full-payment-error">{{error}} <el-button link @click="load">重新加载项目总价</el-button></p>
  </div>
</template>

<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import api from '@/api'
import ReadonlyField from './ReadonlyField.vue'
import {paymentConfirmationForm,paymentChangeEvent} from '@/utils/paymentConfirmation'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {focusFormTarget,scrollFormTarget} from '@/utils/formNavigation'
const props=defineProps({modelValue:Object,projectId:String,prefix:String,fromDetails:Boolean,pricingMode:String,billingTaxMode:String,draftTotals:{type:Array,default:null}})
const emit=defineEmits(['update:modelValue','reference-change'])
const value=computed(()=>paymentConfirmationForm(props.modelValue))
const savedTotals=ref([]),loading=ref(false),error=ref('')
const reasonField=ref(null),editingAmount=ref(false)
const totals=computed(()=>props.draftTotals??savedTotals.value)
let sequence=0,controller
const currencies=computed(()=>[...new Set(['CNY','USD','HKD','EUR','GBP','JPY',...totals.value.map(item=>item.currency)])])
const sameAmount=(a,b)=>Math.round(Number(a)*100)===Math.round(Number(b)*100)
const reference=computed(()=>totals.value.find(item=>item.key===`billing:${value.value.fullPaymentCurrency}`))
const referenceTaxLabel=computed(()=>({incl_tax:'含税',excl_tax:'不含税',mixed:'按子订单计费口径'})[reference.value?.taxMode]||'项目计费口径')
const fixedCharge=computed(()=>props.pricingMode==='fixed')
const referenceFieldLabel=computed(()=>fixedCharge.value?`${({incl_tax:'（含税）',excl_tax:'（不含税）'})[reference.value?.taxMode||props.billingTaxMode]||'（含税/不含税）'}固定收费`:'对应项目总价')
const status=computed(()=>loading.value||value.value.fullPaymentAmount==null?'pending':reference.value&&reference.value.currency===value.value.fullPaymentCurrency&&sameAmount(reference.value.amount,value.value.fullPaymentAmount)?'matched':'mismatch')
const legacy=computed(()=>value.value.fullMatchStatus==='unverified'&&value.value.fullPaymentAmount==null)
function update(key,data){emit('update:modelValue',{...value.value,[key]:data})}
function validateAmount(_rule,_amount,callback){callback(legacy.value?undefined:error.value?new Error('请先重新加载项目总价'):loading.value?new Error('项目总价正在加载'):value.value.fullPaymentAmount==null?new Error('请填写已付全款金额'):undefined)}
async function load(){
  const current=++sequence;controller?.abort();controller=new AbortController();savedTotals.value=[];error.value=''
  if(props.draftTotals!==null){loading.value=false;return}
  if(!props.projectId){error.value='保存项目并登记收费后，可核对全款金额';return}
  loading.value=true
  try{const data=await api.get(`/translation-payments/${props.projectId}/totals`,{signal:controller.signal});if(current===sequence)savedTotals.value=data.items||[]}
  catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目总价加载失败')}
  finally{if(current===sequence)loading.value=false}
}
function onPaymentChanged(event){if(event.detail?.projectId===props.projectId)void load()}
window.addEventListener(paymentChangeEvent,onPaymentChanged)
watch([()=>props.projectId,()=>props.draftTotals],load,{immediate:true,deep:true})
watch([status,reasonField,editingAmount],([match,field,isEditing])=>{
  // 手填全款金额在结束输入后跳转，避免输入中途移走光标。
  if(match!=='mismatch'||isEditing||error.value||value.value.mismatchReason?.trim())return
  const target=field?.$el
  if(!target?.getClientRects().length||!focusFormTarget(target))return
  scrollFormTarget(target)
},{flush:'post'})
watch([totals,()=>value.value.fullPaymentCurrency,loading],()=>{
  if(loading.value)return
  const key=reference.value?.key||null
  if(key!==value.value.fullPaymentTotalKey)emit('reference-change',key)
},{immediate:true})
onBeforeUnmount(()=>{window.removeEventListener(paymentChangeEvent,onPaymentChanged);sequence++;controller?.abort()})
</script>

<style scoped>
.full-payment-reference{display:flex;align-items:center;gap:10px;width:100%;min-width:0}.full-payment-reference>.el-input{flex:1;min-width:0}.full-payment-tax-mode{color:var(--el-color-danger);white-space:nowrap;font-size:13px}
.full-payment-reference-hint{width:100%;margin:6px 0 0;line-height:1.5}
.full-payment-result-row{display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:12px}.full-payment-result-row .full-payment-result{flex:0 1 auto;margin:0;min-height:32px}.full-payment-reason{flex:1 1 300px;min-width:0;margin-bottom:0}.full-payment-reason :deep(.el-form-item__content){min-width:0}.full-payment-reason :deep(.el-textarea){width:100%}
.full-payment-inputs{display:grid;grid-template-columns:1fr .7fr 1.8fr;gap:12px}.full-payment-inputs>*{min-width:0}.full-payment-inputs .el-select,.full-payment-inputs .el-input-number{width:100%}.full-payment-result{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 12px}.full-payment-hint{color:var(--el-text-color-secondary);font-size:12px}.full-payment-error{color:var(--el-color-danger)}@media(max-width:680px){.full-payment-inputs{grid-template-columns:1fr}}
</style>
