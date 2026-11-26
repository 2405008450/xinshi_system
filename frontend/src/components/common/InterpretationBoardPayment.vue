<template>
  <section v-loading="loading||saving" class="oral-board-payment" data-dialog-field-search-group data-dialog-field-search-group-title="对账单付款情况">
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
    <AppForm v-if="form" ref="formRef" :model="form" :disabled="!canWrite||saving||loading" label-position="top" data-auto-draft="off">
      <PaymentRegistrationFields v-model="form" :draft-totals="totals" summary-label="对账单" :history-url="`${url}/history?mode=${mode}`" :currency-options="interpretationCurrencies" :show-deposit-currency="false" :can-confirm="canManageHr()&&canWrite" :confirm-disabled="dirty||saving" @confirm-payment="confirmPayment" />
      <p class="payment-help">{{notice}}</p>
      <el-button v-if="canWrite" type="primary" :disabled="!dirty" @click="save">保存本对账单付款</el-button>
    </AppForm>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import api from '@/api'
import {businessPaymentForm,businessPaymentPayload} from '@/utils/businessFinancePayment'
import {interpretationCurrencies} from '@/utils/interpretationCustomerFinance'
import {canManageHr} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import AppForm from './AppForm.vue'
import PaymentRegistrationFields from './PaymentRegistrationFields.vue'
const props=defineProps({projectId:String,boardId:String,mode:String,version:Number,canWrite:Boolean})
const emit=defineEmits(['saved'])
const form=ref(null),formRef=ref(),totals=ref([]),notice=ref(''),revision=ref(0),loading=ref(false),saving=ref(false),error=ref('')
const url=computed(()=>`/interpretation-customer-finance/statement-payments/${props.projectId}/${props.boardId}`)
const signature=()=>JSON.stringify(form.value&&businessPaymentPayload(form.value))
let original='',controller,sequence=0
const dirty=computed(()=>!!form.value&&signature()!==original)
function apply(data){
  revision.value=data.revision;notice.value=data.notice
  totals.value=Object.entries(data.totals||{}).map(([currency,amount])=>({key:`statement:${currency}`,label:'对账单总价',currency,amount}))
  form.value={...businessPaymentForm(data.registration),pricingMode:'aggregate'}
  const payment=form.value.paymentConfirmation
  if(payment.isPaid&&payment.paymentOption==='deposit'&&!form.value.paymentDraft.length)form.value.paymentDraft.push({currency:payment.fullPaymentCurrency||'CNY',stage_type:'deposit',stage_no:1,payment_method:payment.paymentAccount||'',proofs:payment.proofs||'',payment_time:null})
  if(payment.isPaid&&(payment.paymentOption==='full'||payment.fullPaymentSource==='details'))payment.fullPaymentTotalKey=`statement:${payment.fullPaymentCurrency}`
  original=signature()
}
async function load(){controller?.abort();const request=controller=new AbortController(),seq=++sequence;loading.value=true;error.value='';try{const data=await api.get(url.value,{params:{mode:props.mode},signal:request.signal});if(seq===sequence)apply(data)}catch(e){if(!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'对账单付款加载失败')}finally{if(seq===sequence)loading.value=false}}
async function save(){if(!props.canWrite||saving.value||!dirty.value)return;try{await formRef.value.validate()}catch{return}saving.value=true;error.value='';try{apply(await api.put(url.value,{revision:revision.value,registration:businessPaymentPayload(form.value)},{params:{mode:props.mode}}));emit('saved')}catch(e){error.value=getLocalizedErrorMessage(e,'对账单付款保存失败')}finally{saving.value=false}}
async function confirmPayment(paymentId){if(dirty.value||saving.value||!props.canWrite)return;saving.value=true;error.value='';try{apply(await api.post(`${url.value}/confirm`,{revision:revision.value,payment_id:paymentId},{params:{mode:props.mode}}));emit('saved')}catch(e){error.value=getLocalizedErrorMessage(e,'付款确认失败')}finally{saving.value=false}}
watch(()=>[props.projectId,props.boardId,props.mode],()=>{form.value=null;void load()},{immediate:true})
watch(()=>props.version,()=>{if(!saving.value&&!dirty.value)void load()})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>.oral-board-payment{border:1px solid var(--el-border-color);border-radius:8px;padding:14px;margin:12px 0}.payment-help{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}</style>
