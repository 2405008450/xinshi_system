import {businessDateTimeInputValue} from './dateTime.js'

export const currentStatementMonth=()=>businessDateTimeInputValue().slice(0,7)
export function orderStatementMonth(orderNo){const match=String(orderNo||'').match(/^TP-(\d{8}|\d{6})-/i);if(!match)return '';const value=match[1],month=value.length===8?value.slice(4,6):value.slice(2,4);if(Number(month)<1||Number(month)>12)return '';return value.length===8?`${value.slice(0,4)}-${value.slice(4,6)}`:`20${value.slice(0,2)}-${value.slice(2,4)}`}
export function previousStatementMonth(month=currentStatementMonth()){
  const [year,value]=month.split('-').map(Number)
  return value===1?`${year-1}-12`:`${year}-${String(value-1).padStart(2,'0')}`
}
