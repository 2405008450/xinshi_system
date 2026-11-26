import {paymentConfirmationForm,paymentConfirmationPayload} from './paymentConfirmation.js'
import {paymentDetailsForm,paymentDetailsPayload} from './paymentDetails.js'

export function businessPaymentForm(value={}) {
  return {
    paymentConfirmation:paymentConfirmationForm(value.confirmation),
    paymentLegacyFullReceivedOn:value.full_payment_received_on||null,
    paymentDraft:paymentDetailsForm(value.payments||[]).map((row,index)=>({...row,currency:value.payments[index].currency||'CNY'})),
  }
}
export function businessPaymentPayload(form) {
  return {
    confirmation:paymentConfirmationPayload(form.paymentConfirmation),
    full_payment_received_on:form.paymentLegacyFullReceivedOn||null,
    payments:paymentDetailsPayload(form.paymentDraft).map((row,index)=>({...row,currency:form.paymentDraft[index].currency||form.paymentConfirmation.fullPaymentCurrency||'CNY'})),
  }
}
