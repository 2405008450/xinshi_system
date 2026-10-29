import {reportBusinessDate,shiftReportDate} from './workReportForm.js'
export function arrangementDateRange(key,anchor=reportBusinessDate()){
  if(key==='today')return null
  if(key==='yesterday'||key==='before-yesterday'){const day=shiftReportDate(anchor,key==='yesterday'?-1:-2);return [day,day]}
  const weekday=new Date(`${anchor}T12:00:00+08:00`).getUTCDay()
  const monday=shiftReportDate(anchor,-((weekday+6)%7))
  if(key==='last-week')return [shiftReportDate(monday,-7),shiftReportDate(monday,-1)]
  if(key==='previous-week')return [shiftReportDate(monday,-14),shiftReportDate(monday,-8)]
  return null
}
