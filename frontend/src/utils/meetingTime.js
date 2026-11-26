export function meetingLeadMinutes(start,end){const minutes=(Date.parse(end)-Date.parse(start))/60000;return minutes<=30?10:minutes<=60?15:20}
export function meetingCountdown(meeting,now=Date.now()){
 const start=Date.parse(meeting.start_at),end=Date.parse(meeting.end_at)
 const status=meeting.status||'pending'
 if(status==='ended'||status==='cancelled')return ''
 if(status==='in_progress'){
  const actualStart=Date.parse(meeting.status_started_at)
  if(!Number.isFinite(actualStart))return '会议进行中'
  const remaining=(end-start)-Math.max(0,now-actualStart)
  const seconds=Math.ceil(Math.abs(remaining)/1000)
  return `${remaining>0?'会议剩余':'会议已超时'} ${Math.floor(seconds/60)}分${String(seconds%60).padStart(2,'0')}秒`
 }
 if(now>=end)return ''
 if(now>=start)return '已到计划开始时间，等待召开人开始'
 const remaining=start-now,lead=meeting.remind_before_minutes??meetingLeadMinutes(meeting.start_at,meeting.end_at)
 if(remaining>lead*60000)return ''
 return '会议即将开始，等待召开人开始'
}
export const meetingStamp=value=>value?value.replace(' ','T').replace(/(?:Z|[+-]\d\d:\d\d)$/,'')+'+08:00':null
