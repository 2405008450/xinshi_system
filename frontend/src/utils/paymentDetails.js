import {businessDateTimeInputValue} from './dateTime.js'

export function paymentDetailsForm(rows=[]){
  return rows.map((row,index)=>({id:row.id||undefined,stage_type:row.stage_type??row.stageType??'deposit',stage_no:index+1,
    planned_amount:(row.planned_amount??row.plannedAmount)==null?undefined:Number(row.planned_amount??row.plannedAmount),
    actual_amount:(row.actual_amount??row.actualAmount)==null?undefined:Number(row.actual_amount??row.actualAmount),
    payment_time:(row.payment_time??row.paymentTime)?businessDateTimeInputValue(row.payment_time??row.paymentTime):null,
    payment_method:row.payment_method??row.paymentMethod??'',proofs:row.proofs||'',
    confirmed_by_name:row.confirmed_by_name??row.confirmedByName??null,
    confirmed_at:row.confirmed_at??row.confirmedAt??null}))
}
export function paymentDetailsPayload(rows=[]){
  return paymentDetailsForm(rows).map(({confirmed_by_name,confirmed_at,...row})=>({...row,planned_amount:row.planned_amount??null,actual_amount:row.actual_amount??null,
    payment_time:row.payment_time?row.payment_time.replace(' ','T')+'+08:00':null}))
}
export const paymentDetailsSignature=rows=>JSON.stringify(paymentDetailsPayload(rows))
