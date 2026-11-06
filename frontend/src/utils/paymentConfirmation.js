export const paymentOptions=[{value:'deposit',label:'已付定金'},{value:'full',label:'已付全款'}]
export function paymentConfirmationForm(value){
  const isPaid=!!(value?.isPaid??value?.is_paid),paymentOption=value?.paymentOption??value?.payment_option??null
  const amount=value?.fullPaymentAmount??value?.full_payment_amount
  return {revision:value?.revision||0,isPaid,paymentOption,paymentAccount:value?.paymentAccount??value?.payment_account??'',proofs:value?.proofs||'',
    fullPaymentSource:value?.fullPaymentSource??value?.full_payment_source??null,fullPaymentAmount:amount==null?null:Number(amount),fullPaymentCurrency:value?.fullPaymentCurrency??value?.full_payment_currency??'CNY',
    fullPaymentTotalKey:value?.fullPaymentTotalKey??value?.full_payment_total_key??null,mismatchReason:value?.mismatchReason??value?.mismatch_reason??'',
    fullMatchStatus:value?.fullMatchStatus??value?.full_match_status??(isPaid&&paymentOption==='full'?'unverified':'none'),
    fullReferenceLabel:value?.fullReferenceLabel??value?.full_reference_label??'',fullReferenceAmount:value?.fullReferenceAmount??value?.full_reference_amount??null}
}
export function paymentConfirmationPayload(value){const item=paymentConfirmationForm(value);return {revision:item.revision,is_paid:item.isPaid,payment_option:item.paymentOption,payment_account:item.paymentAccount,proofs:item.proofs,full_payment_amount:item.fullPaymentAmount,full_payment_currency:item.fullPaymentCurrency,full_payment_total_key:item.fullPaymentTotalKey,mismatch_reason:item.mismatchReason}}
export function paymentConfirmationLabel(value){const item=paymentConfirmationForm(value);return (item.isPaid?(paymentOptions.find(option=>option.value===item.paymentOption)?.label||(item.paymentOption==='once'?'已登记分次付款':'已付款')):'未确认付款')+(item.paymentAccount?' · '+item.paymentAccount:'')+((item.paymentOption==='full'||item.fullPaymentSource==='details')&&item.fullPaymentAmount!=null?` · ${item.fullPaymentCurrency} ${item.fullPaymentAmount.toFixed(2)}`:'')+(item.fullMatchStatus==='mismatch'?` · 不匹配：${item.mismatchReason}`:item.fullMatchStatus==='matched'?` · 匹配${item.fullReferenceLabel} ${item.fullReferenceAmount}`:'')}
export const paymentChangeEvent='translation-payment-changed'
export function notifyPaymentChanged(projectId,confirmation,source=''){window.dispatchEvent(new CustomEvent(paymentChangeEvent,{detail:{projectId:String(projectId),confirmation:paymentConfirmationForm(confirmation),source}}))}
