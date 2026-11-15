<template>
  <AppForm v-loading="loading" ref="formRef" :model="form" label-position="top" :disabled="!canWrite||saving||loading">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <PaymentRegistrationFields v-if="ready" v-model="form" :draft-totals="totals"
      summary-label="客户原始计费" prefix="paymentConfirmation" />
    <el-button v-if="ready&&canWrite" type="primary" :loading="saving" :disabled="!dirty" @click="save">保存付款情况</el-button>
    <el-button v-if="!ready&&error" @click="load">重新加载</el-button>
  </AppForm>
</template>

<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {paymentConfirmationForm,paymentConfirmationPayload} from '@/utils/paymentConfirmation'
import {paymentDetailsForm,paymentDetailsPayload} from '@/utils/paymentDetails'
import AppForm from './AppForm.vue'
import PaymentRegistrationFields from './PaymentRegistrationFields.vue'

const props=defineProps({clientId:String,month:String,periodNumber:Number,originalTotals:Object})
const emit=defineEmits(['saved'])
const canWrite=hasPermission('projects:write')
const formRef=ref(),form=ref({paymentConfirmation:paymentConfirmationForm(),paymentDraft:[]})
const ready=ref(false),loading=ref(false),saving=ref(false),error=ref(''),revision=ref(0),original=ref('')
const endpoint=computed(()=>`/translation-statement-workspaces/${props.clientId}/special-payment/${props.month}`)
const params=computed(()=>({period_number:props.periodNumber}))
const totals=computed(()=>Object.entries(props.originalTotals?.billingTotals||{}).map(([currency,amount])=>
  ({key:`billing:${currency}`,label:'客户原始计费总价',currency,amount})))
const signature=()=>JSON.stringify([form.value.paymentConfirmation.isPaid,form.value.paymentConfirmation.paymentOption,
  form.value.paymentConfirmation.paymentAccount,form.value.paymentConfirmation.proofs,form.value.paymentConfirmation.fullPaymentAmount,
  form.value.paymentConfirmation.fullPaymentCurrency,form.value.paymentConfirmation.mismatchReason,paymentDetailsPayload(form.value.paymentDraft)])
const dirty=computed(()=>signature()!==original.value)
let controller,context=0

function apply(data){
  form.value={paymentConfirmation:paymentConfirmationForm(data.confirmation),paymentDraft:paymentDetailsForm(data.payments)}
  revision.value=data.revision
  original.value=signature()
  ready.value=true
}
async function load(){
  const current=++context
  controller?.abort()
  controller=new AbortController()
  ready.value=false
  error.value=''
  if(!props.clientId||!props.month)return
  loading.value=true
  try{
    const data=await api.get(endpoint.value,{params:params.value,signal:controller.signal})
    if(current===context)apply(data)
  }catch(e){
    if(current===context)error.value=getLocalizedErrorMessage(e,'特殊结算付款情况加载失败')
  }finally{if(current===context)loading.value=false}
}
async function save(){
  if(saving.value||!await formRef.value?.validate().catch(()=>false))return
  const current=context
  saving.value=true
  error.value=''
  try{
    const data=await api.put(endpoint.value,{revision:revision.value,confirmation:paymentConfirmationPayload(form.value.paymentConfirmation),
      payments:paymentDetailsPayload(form.value.paymentDraft)},{params:params.value})
    if(current===context){
      apply(data)
      ElMessage.success('特殊结算付款情况已保存')
      emit('saved')
    }
  }catch(e){
    if(current===context)error.value=getLocalizedErrorMessage(e,'特殊结算付款情况保存失败')
  }finally{saving.value=false}
}
watch(()=>[props.clientId,props.month,props.periodNumber],load,{immediate:true})
onBeforeUnmount(()=>{context++;controller?.abort()})
</script>
