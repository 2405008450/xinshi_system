import {businessDateTimeInputValue} from './dateTime.js'
export function currentShiftMonth(now=new Date()){return businessDateTimeInputValue(now).slice(0,7)}
export function shiftMonth(month,offset){const [year,value]=month.split('-').map(Number);const date=new Date(Date.UTC(year,value-1+offset,1));return `${date.getUTCFullYear()}-${String(date.getUTCMonth()+1).padStart(2,'0')}`}
export const shiftMonthTitle=month=>`${month.slice(0,4)}年${Number(month.slice(5))}月班次安排`
export function shiftWeek(value,offset=0){const date=new Date(`${value}T12:00:00Z`);date.setUTCDate(date.getUTCDate()-((date.getUTCDay()+6)%7)+offset*7);return date.toISOString().slice(0,10)}
export function currentShiftWeek(now=new Date()){return shiftWeek(businessDateTimeInputValue(now).slice(0,10))}
export function shiftWeekEnd(value){const date=new Date(`${shiftWeek(value)}T12:00:00Z`);date.setUTCDate(date.getUTCDate()+6);return date.toISOString().slice(0,10)}
export const shiftWeekTitle=week=>`${shiftWeek(week)} 至 ${shiftWeekEnd(week)} 班次安排`
// 月视图包含与月份有交集的完整自然周，跨月周保持同一份安排。
export function shiftMonthWeeks(month){
 const end=`${shiftMonth(month,1)}-01`,weeks=[]
 for(let week=shiftWeek(`${month}-01`);week<end;week=shiftWeek(week,1))weeks.push(week)
 return weeks
}
