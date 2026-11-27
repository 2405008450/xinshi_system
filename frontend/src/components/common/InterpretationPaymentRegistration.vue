<template>
  <PaymentRegistrationFields :model-value="paymentModel" class="finance-region" :draft-totals="totals" :currency-options="interpretationCurrencies" :show-deposit-currency="false"
    :history-url="projectId?`/interpretation-customer-finance/project/${projectId}/payment-history`:''"
    :can-confirm="canConfirm" :confirm-disabled="confirmDisabled" @confirm-payment="$emit('confirm-payment',$event)">
    <template #actions><el-button :disabled="!projectId" @click="invoiceVisible=true">打开发票</el-button></template>
    <template v-if="!projectId" #footer><p class="payment-help">保存项目后可打开完整付款情况。</p></template>
  </PaymentRegistrationFields>
  <InterpretationInvoiceDialog v-if="invoiceVisible" v-model="invoiceVisible" :project-id="projectId" :can-write="canWrite" @saved="$emit('invoice-saved')" />
</template>
<script setup>
import {computed,ref} from 'vue'
import PaymentRegistrationFields from './PaymentRegistrationFields.vue'
import InterpretationInvoiceDialog from './InterpretationInvoiceDialog.vue'
import {interpretationCurrencies,interpretationFinanceTotals} from '@/utils/interpretationCustomerFinance'
const model=defineModel({type:Object,required:true})
defineProps({projectId:String,canWrite:Boolean,canConfirm:Boolean,confirmDisabled:Boolean})
defineEmits(['confirm-payment','invoice-saved'])
const invoiceVisible=ref(false)
const paymentModel=computed(()=>({
  get paymentConfirmation(){return model.value.paymentConfirmation},
  set paymentConfirmation(value){model.value.paymentConfirmation=value},
  get paymentDraft(){return model.value.paymentDraft},
  set paymentDraft(value){model.value.paymentDraft=value},
  pricingMode:model.value.settlement.pricing_mode,billingTaxMode:model.value.settlement.tax_basis,
}))
const totals=computed(()=>Object.entries(interpretationFinanceTotals(model.value)).map(([currency,amount])=>({key:`billing:${currency}`,label:'项目计费金额',currency,amount,taxMode:model.value.settlement.tax_basis})))
</script>
<style scoped>.finance-region{padding:18px;border:1px solid var(--el-border-color);border-radius:8px;margin:18px 0}.payment-help{font-size:12px;color:var(--el-text-color-secondary);margin:8px 0 0}</style>
