import {businessDateTimeInputValue} from './dateTime.js'
export const DEFAULT_ARRANGEMENT_EXCLUSIONS=['pending_confirmation','sent_to_client','feedback_sent_to_client','paused','cancelled']
// UTC+8 日历日期；凌晨确认，不按日报七点换日规则悄悄减一天。
export function arrangementDeadlineShortcut(kind,now=new Date()) {
  const local=businessDateTimeInputValue(now),today=local.slice(0,10)
  const next=new Date(`${today}T00:00:00+08:00`);next.setUTCDate(next.getUTCDate()+1)
  const tomorrow=businessDateTimeInputValue(next).slice(0,10),isToday=kind==='today'
  return {range:isToday?[today,today]:['',tomorrow],date:isToday?today:tomorrow,word:isToday?'今天':'明天',needsConfirmation:Number(local.slice(11,13))<7}
}
export function withArrangementExclusions(serialized,exclusions) {
  const filters=serialized?JSON.parse(serialized):{}
  if(exclusions.length)filters.excluded_project_status={op:'in',value:[...exclusions]}
  return Object.keys(filters).length?JSON.stringify(filters):undefined
}
