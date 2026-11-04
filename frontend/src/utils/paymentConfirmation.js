export const paymentOptions=[{value:'full',label:'已支付全款'},{value:'deposit',label:'已支付定金'},{value:'once',label:'已支付一次款'}]
export function paymentConfirmationForm(value){return {revision:value?.revision||0,isPaid:!!(value?.isPaid??value?.is_paid),paymentOption:value?.paymentOption??value?.payment_option??null,proofs:value?.proofs||''}}
export function paymentConfirmationPayload(value){const item=paymentConfirmationForm(value);return {revision:item.revision,is_paid:item.isPaid,payment_option:item.paymentOption,proofs:item.proofs}}
export function paymentConfirmationLabel(value){const item=paymentConfirmationForm(value);return item.isPaid?(paymentOptions.find(option=>option.value===item.paymentOption)?.label||'已付款'):'未勾选付款'}
