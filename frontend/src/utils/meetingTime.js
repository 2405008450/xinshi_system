export function meetingLeadMinutes(start,end){const minutes=(Date.parse(end)-Date.parse(start))/60000;return minutes<=30?10:minutes<=60?15:20}
export function meetingCountdown(meeting,now=Date.now()){
 const start=Date.parse(meeting.start_at),end=Date.parse(meeting.end_at)
 if(now>=end)return ''
 if(now>=start)return '会议进行中'
 const remaining=start-now,lead=meeting.remind_before_minutes??meetingLeadMinutes(meeting.start_at,meeting.end_at)
 if(remaining>lead*60000)return ''
 const seconds=Math.ceil(remaining/1000)
 return `距会议开始 ${Math.floor(seconds/60)}分${String(seconds%60).padStart(2,'0')}秒`
}
export const meetingStamp=value=>value?value.replace(' ','T').replace(/(?:Z|[+-]\d\d:\d\d)$/,'')+'+08:00':null
