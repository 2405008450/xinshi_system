export const paymentOptions=[{value:'deposit',label:'已付定金'},{value:'full',label:'已付全款'}]
export const paymentStatusLabels={unpaid:'未付款',deposit:'已付定金',mid:'已付进度款',full:'已付全款'}
export const paymentStatusFilterOptions=[{value:'unpaid',label:'未付款'},{value:'deposit',label:'已付定金'},{value:'mid',label:'已付进度款'},{value:'full',label:'已付全款（含尾款）'},{value:'paid',label:'已付款（含部分）'}]
export async function switchPaymentSelection(value,option,{payments=[],confirm}){
  const current=paymentConfirmationForm(value)
  if(current.isPaid&&current.paymentOption===option)return null
  const hasDetails=payments.some(row=>row.planned_amount!=null||row.actual_amount!=null||row.payment_method||row.payment_time||row.proofs)
  const hasFull=current.fullPaymentSource!=='details'&&(current.fullPaymentAmount!=null||current.fullPaymentTotalKey||current.mismatchReason)
  const hasShared=!!(current.paymentAccount||current.proofs)
  const other=option==='full'?(hasDetails||(current.paymentOption==='deposit'&&hasShared)):(hasFull||((current.paymentOption==='full'||!current.isPaid)&&hasShared))
  if(other){
    const target=option==='full'?'已付全款':'已付定金',previous=option==='full'?'已付定金':'已付全款'
    try{await confirm(`已付定金/已付全款，只能选择填写其一。选择${target}，将自动清除${previous}的付款数据，请问是否继续？`)}catch{return null}
  }
  const next=other?clearPaymentSelection(current):current
  return {...next,isPaid:true,paymentOption:option,clearDetails:false,replaceDetails:current.replaceDetails||current.clearDetails||other,fullMatchStatus:option==='full'?'pending':'none'}
}
export function clearPaymentSelection(value){return {...paymentConfirmationForm(value),isPaid:false,paymentOption:null,paymentAccount:'',proofs:'',fullPaymentSource:null,fullPaymentAmount:null,fullPaymentTotalKey:null,fullMatchStatus:'none',fullReferenceLabel:'',fullReferenceAmount:null,fullPaymentConfirmedByName:null,fullPaymentConfirmedAt:null,mismatchReason:'',clearDetails:true}}
export function fixFirstDepositStage(confirmation,payments){
  if(!confirmation?.isPaid||confirmation.paymentOption!=='deposit'||!payments.length)return
  payments[0].stage_type='deposit'
}
// 先保留人工已选项；首次进入或切换币种时，优先采用流程靠后的总价。
export function preferredPaymentTotalKey(totals,currency,currentKey){
  const candidates=(totals||[]).filter(item=>item.currency===currency)
  if(candidates.some(item=>item.key===currentKey))return currentKey
  const priority={excl:1,incl:2,adjusted:3,billing:4}
  return candidates.reduce((selected,item)=>!selected||(priority[item.key.split(':')[0]]||0)>=(priority[selected.key.split(':')[0]]||0)?item:selected,null)?.key||null
}
export function paymentConfirmationForm(value){
  const isPaid=!!(value?.isPaid??value?.is_paid),paymentOption=value?.paymentOption??value?.payment_option??null
  const amount=value?.fullPaymentAmount??value?.full_payment_amount
  return {revision:value?.revision||0,clearDetails:!!(value?.clearDetails??value?.clear_details),replaceDetails:!!(value?.replaceDetails??value?.replace_details),isPaid,paymentOption,paymentAccount:value?.paymentAccount??value?.payment_account??'',proofs:value?.proofs||'',
    fullPaymentSource:value?.fullPaymentSource??value?.full_payment_source??null,fullPaymentAmount:amount==null?null:Number(amount),fullPaymentCurrency:value?.fullPaymentCurrency??value?.full_payment_currency??'CNY',
    fullPaymentTotalKey:value?.fullPaymentTotalKey??value?.full_payment_total_key??null,mismatchReason:value?.mismatchReason??value?.mismatch_reason??'',
    fullMatchStatus:value?.fullMatchStatus??value?.full_match_status??(isPaid&&paymentOption==='full'?'unverified':'none'),
    fullPaymentConfirmedByName:value?.fullPaymentConfirmedByName??value?.full_payment_confirmed_by_name??null,
    fullPaymentConfirmedAt:value?.fullPaymentConfirmedAt??value?.full_payment_confirmed_at??null,
    fullReferenceLabel:value?.fullReferenceLabel??value?.full_reference_label??'',fullReferenceAmount:value?.fullReferenceAmount??value?.full_reference_amount??null}
}
export function paymentConfirmationPayload(value){const item=paymentConfirmationForm(value);return {revision:item.revision,clear_details:item.clearDetails,replace_details:item.replaceDetails,is_paid:item.isPaid,payment_option:item.paymentOption,payment_account:item.paymentAccount,proofs:item.proofs,full_payment_amount:item.fullPaymentAmount,full_payment_currency:item.fullPaymentCurrency,full_payment_total_key:item.fullPaymentTotalKey,mismatch_reason:item.mismatchReason}}
export function paymentConfirmationLabel(value){const item=paymentConfirmationForm(value);return (item.isPaid?(paymentOptions.find(option=>option.value===item.paymentOption)?.label||(item.paymentOption==='once'?'已登记分次付款':'已付款')):'未确认付款')+(item.paymentAccount?' · '+item.paymentAccount:'')+((item.paymentOption==='full'||item.fullPaymentSource==='details')&&item.fullPaymentAmount!=null?` · ${item.fullPaymentCurrency} ${item.fullPaymentAmount.toFixed(2)}`:'')+(item.fullMatchStatus==='mismatch'?` · 不匹配：${item.mismatchReason}`:item.fullMatchStatus==='matched'?` · 匹配${item.fullReferenceLabel} ${item.fullReferenceAmount}`:'')}
export const paymentChangeEvent='translation-payment-changed'
let paymentSyncChannel
export function connectPaymentSync(){
  if(!paymentSyncChannel&&typeof window.BroadcastChannel==='function'){
    paymentSyncChannel=new window.BroadcastChannel('translation-finance-payment-sync')
    paymentSyncChannel.onmessage=event=>{const detail=event.data;if(detail?.projectId)window.dispatchEvent(new CustomEvent(paymentChangeEvent,{detail}))}
  }
}
export function notifyPaymentChanged(projectId,confirmation,source=''){
  connectPaymentSync()
  const detail={projectId:String(projectId),confirmation:paymentConfirmationForm(confirmation),source}
  window.dispatchEvent(new CustomEvent(paymentChangeEvent,{detail}))
  paymentSyncChannel?.postMessage(detail)
}
