import {reportBusinessDate,shiftReportDate} from './workReportForm.js'
export const receivedReportDatePresets=[
  {key:'today',label:'今日'},
  {key:'yesterday',label:'昨日'},
  {key:'before-yesterday',label:'前日'},
  {key:'three-days-ago',label:'大前天'},
  {key:'last-week',label:'上周'},
  {key:'last-month',label:'上个月'},
  {key:'all',label:'全部日期'},
]
export function receivedReportDateRange(key,anchor=new Date(Date.now()+8*3600000).toISOString().slice(0,10)){
  if(key==='all')return []
  const offsets={'today':0,'yesterday':-1,'before-yesterday':-2,'three-days-ago':-3}
  if(key in offsets){const day=shiftReportDate(anchor,offsets[key]);return [day,day]}
  if(key==='last-week')return arrangementDateRange(key,anchor)
  if(key==='last-month'){
    const end=shiftReportDate(anchor.slice(0,7)+'-01',-1)
    return [end.slice(0,7)+'-01',end]
  }
  return []
}
export function defaultReceivedReportDateRange(now=Date.now()){
  const shifted=new Date(new Date(now).getTime()+8*3600000)
  const day=shifted.toISOString().slice(0,10)
  return receivedReportDateRange(shifted.getUTCHours()<18?'yesterday':'today',day)
}
export function arrangementDateRange(key,anchor=reportBusinessDate()){
  if(key==='today')return null
  if(key==='yesterday'||key==='before-yesterday'){const day=shiftReportDate(anchor,key==='yesterday'?-1:-2);return [day,day]}
  const weekday=new Date(`${anchor}T12:00:00+08:00`).getUTCDay()
  const monday=shiftReportDate(anchor,-((weekday+6)%7))
  if(key==='last-week')return [shiftReportDate(monday,-7),shiftReportDate(monday,-1)]
  if(key==='previous-week')return [shiftReportDate(monday,-14),shiftReportDate(monday,-8)]
  return null
}
