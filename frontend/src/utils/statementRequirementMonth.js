import {businessDateTimeInputValue} from './dateTime.js'

export const currentStatementMonth=()=>businessDateTimeInputValue().slice(0,7)
export function previousStatementMonth(month=currentStatementMonth()){
  const [year,value]=month.split('-').map(Number)
  return value===1?`${year-1}-12`:`${year}-${String(value-1).padStart(2,'0')}`
}
