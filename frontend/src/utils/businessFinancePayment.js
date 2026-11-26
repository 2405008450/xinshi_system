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

// 旧口译账簿只读转换：保留原收款金额、日期、币种和备注。
export function legacyBusinessPaymentRegistration(payload={}) {
  if(payload.payment_registration)return payload.payment_registration
  const settlement=payload.settlement||{},rows=settlement.payments||[]
  const paid=settlement.payment_status&&settlement.payment_status!=='unrecorded'||rows.length>0
  const full=settlement.payment_status==='full'&&rows.length<=1
  return {
    confirmation:{is_paid:!!paid,payment_option:paid?(full?'full':'deposit'):null,
      full_payment_currency:rows[0]?.currency||payload.rates?.[0]?.currency||'CNY',
      full_payment_amount:full?rows[0]?.amount??null:null,
      proofs:[settlement.payment_note,full?rows[0]?.note:''].filter(Boolean).join('\n')},
    payments:full?[]:rows.map((row,index)=>({stage_type:index===0?'deposit':row.stage_type==='tail'?'final':'mid',
      stage_no:index+1,actual_amount:row.amount,currency:row.currency,payment_time:row.received_on?`${row.received_on}T00:00:00+08:00`:null,proofs:row.note||''})),
    full_payment_received_on:full?rows[0]?.received_on||null:null,
  }
}
