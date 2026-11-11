import {businessDateTimeInputValue} from './dateTime.js'

export function paymentDetailsForm(rows=[]){
  return rows.map(row=>({id:row.id||undefined,stage_type:row.stage_type??row.stageType??'deposit',stage_no:Number(row.stage_no??row.stageNo??1),
    planned_amount:(row.planned_amount??row.plannedAmount)==null?undefined:Number(row.planned_amount??row.plannedAmount),
    actual_amount:(row.actual_amount??row.actualAmount)==null?undefined:Number(row.actual_amount??row.actualAmount),
    payment_time:(row.payment_time??row.paymentTime)?businessDateTimeInputValue(row.payment_time??row.paymentTime):null,
    payment_method:row.payment_method??row.paymentMethod??'',proofs:row.proofs||''}))
}
export function paymentDetailsPayload(rows=[]){
  return paymentDetailsForm(rows).map(row=>({...row,planned_amount:row.planned_amount??null,actual_amount:row.actual_amount??null,
    payment_time:row.payment_time?row.payment_time.replace(' ','T')+'+08:00':null}))
}
export const paymentDetailsSignature=rows=>JSON.stringify(paymentDetailsPayload(rows))
