<template>
  <div class="full-payment-match" v-loading="loading">
    <div class="full-payment-inputs">
      <el-form-item :label="fromDetails?'累计实付金额':'已付全款金额'" :prop="`${prefix}.fullPaymentAmount`" :rules="[{validator:validateAmount,trigger:'change'}]"><ReadonlyField v-if="fromDetails" :model-value="value.fullPaymentAmount==null?'待填写各次实际金额':value.fullPaymentAmount.toFixed(2)" source="auto" /><el-input-number v-else :model-value="value.fullPaymentAmount??undefined" :min="0" :precision="2" :controls="false" :aria-label="fromDetails?'累计实付金额':'已付全款金额'" @update:model-value="update('fullPaymentAmount',$event??null)" /></el-form-item>
      <el-form-item label="付款币种"><el-select :model-value="value.fullPaymentCurrency" aria-label="付款币种" @update:model-value="update('fullPaymentCurrency',$event)"><el-option v-for="currency in currencies" :key="currency" :value="currency" /></el-select></el-form-item>
      <el-form-item label="对应项目总价"><el-select :model-value="value.fullPaymentTotalKey" placeholder="选择要比对的项目总价" aria-label="对应项目总价" clearable @update:model-value="update('fullPaymentTotalKey',$event||null)"><el-option v-for="item in totals" :key="item.key" :value="item.key" :label="`${item.label} · ${item.currency} ${item.amount}`" /></el-select></el-form-item>
    </div>
    <p class="full-payment-result"><el-tag :type="status==='matched'?'success':status==='mismatch'?'danger':'info'">{{status==='matched'?'已匹配':status==='mismatch'?'不匹配':'待核对'}}</el-tag><span v-if="reference">{{reference.label}}：{{reference.currency}} {{reference.amount}}</span><span v-else>项目暂无可匹配总价</span></p>
    <p v-if="legacy" class="full-payment-hint">历史全款确认未登记金额，补充金额后可核对项目总价。</p>
    <el-form-item v-if="status==='mismatch'" data-screenshot-editor="own" label="不匹配原因" :prop="`${prefix}.mismatchReason`" :rules="[{required:true,whitespace:true,message:'请说明全款金额不匹配的原因',trigger:'blur'}]"><el-input :model-value="value.mismatchReason" type="textarea" :rows="2" maxlength="2000" show-word-limit aria-label="不匹配原因" @update:model-value="update('mismatchReason',$event)" /></el-form-item>
    <p v-if="error" class="full-payment-error">{{error}} <el-button link @click="load">重新加载项目总价</el-button></p>
  </div>
</template>

<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import api from '@/api'
import ReadonlyField from './ReadonlyField.vue'
import {paymentConfirmationForm,paymentChangeEvent} from '@/utils/paymentConfirmation'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Object,projectId:String,prefix:String,fromDetails:Boolean})
const emit=defineEmits(['update:modelValue'])
const value=computed(()=>paymentConfirmationForm(props.modelValue))
const totals=ref([]),loading=ref(false),error=ref('')
let sequence=0,controller
const currencies=computed(()=>[...new Set(['CNY','USD','HKD','EUR','GBP','JPY',...totals.value.map(item=>item.currency)])])
const sameAmount=(a,b)=>Math.round(Number(a)*100)===Math.round(Number(b)*100)
const reference=computed(()=>totals.value.find(item=>item.key===value.value.fullPaymentTotalKey)||totals.value.find(item=>item.currency===value.value.fullPaymentCurrency&&value.value.fullPaymentAmount!=null&&sameAmount(item.amount,value.value.fullPaymentAmount)))
const status=computed(()=>loading.value||value.value.fullPaymentAmount==null?'pending':reference.value&&reference.value.currency===value.value.fullPaymentCurrency&&sameAmount(reference.value.amount,value.value.fullPaymentAmount)?'matched':'mismatch')
const legacy=computed(()=>value.value.fullMatchStatus==='unverified'&&value.value.fullPaymentAmount==null)
function update(key,data){emit('update:modelValue',{...value.value,[key]:data})}
function validateAmount(_rule,_amount,callback){callback(legacy.value?undefined:error.value?new Error('请先重新加载项目总价'):loading.value?new Error('项目总价正在加载'):value.value.fullPaymentAmount==null?new Error('请填写已付全款金额'):undefined)}
async function load(){
  const current=++sequence;controller?.abort();controller=new AbortController();totals.value=[];error.value=''
  if(!props.projectId){error.value='保存项目并登记收费后，可核对全款金额';return}
  loading.value=true
  try{const data=await api.get(`/translation-payments/${props.projectId}/totals`,{signal:controller.signal});if(current===sequence)totals.value=data.items||[]}
  catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目总价加载失败')}
  finally{if(current===sequence)loading.value=false}
}
function onPaymentChanged(event){if(event.detail?.projectId===props.projectId)void load()}
window.addEventListener(paymentChangeEvent,onPaymentChanged)
watch(()=>props.projectId,load,{immediate:true})
onBeforeUnmount(()=>{window.removeEventListener(paymentChangeEvent,onPaymentChanged);sequence++;controller?.abort()})
</script>

<style scoped>
.full-payment-inputs{display:grid;grid-template-columns:1fr .7fr 1.8fr;gap:12px}.full-payment-inputs>*{min-width:0}.full-payment-inputs .el-select,.full-payment-inputs .el-input-number{width:100%}.full-payment-result{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 12px}.full-payment-hint{color:var(--el-text-color-secondary);font-size:12px}.full-payment-error{color:var(--el-color-danger)}@media(max-width:680px){.full-payment-inputs{grid-template-columns:1fr}}
</style>
