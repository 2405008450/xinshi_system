import {businessDateTimeInputValue} from './dateTime.js'
const endOfMonth=(year,month)=>new Date(Date.UTC(year,month,0)).getUTCDate()
const iso=(year,month,day)=>`${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`
const initialGrant=hireDate=>hireDate.slice(5)<='06-30'?hireDate:Number(hireDate.slice(0,4))<9999?iso(Number(hireDate.slice(0,4))+1,1,1):null
export function annualLeaveGrantDate(hireDate,years){
  const [hireYear,month,day]=hireDate.split('-').map(Number),anniversaryYear=hireYear+years
  const anniversaryDay=Math.min(day,endOfMonth(anniversaryYear,month)),index=anniversaryYear*12+month-1+3,year=Math.floor(index/12),targetMonth=index%12+1
  if(year>9999)return null
  return iso(year,targetMonth,Math.min(anniversaryDay,endOfMonth(year,targetMonth)))
}
export function annualLeaveDays(hireDate,onDate=businessDateTimeInputValue(new Date()).slice(0,10)){
  if(!hireDate)return null
  if(hireDate>onDate)return 0
  const initial=initialGrant(hireDate)
  let days=initial&&initial<=onDate?1:0
  for(let years=1;years<=10;years++){const grant=annualLeaveGrantDate(hireDate,years);if(grant&&grant<=onDate)days++}
  return Math.min(10,days)
}
export function nextAnnualLeaveIncrease(hireDate,onDate=businessDateTimeInputValue(new Date()).slice(0,10)){
  if(!hireDate||annualLeaveDays(hireDate,onDate)>=10)return null
  const initial=initialGrant(hireDate)
  if(initial&&initial>onDate)return initial
  for(let years=1;years<=10;years++){const day=annualLeaveGrantDate(hireDate,years);if(day&&day>onDate)return day}
  return null
}
export const annualLeaveDateLabel=value=>value?`${value.slice(0,4)}年${Number(value.slice(5,7))}月${Number(value.slice(8,10))}日`:'-'
