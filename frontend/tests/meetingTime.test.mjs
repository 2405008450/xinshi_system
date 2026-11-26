import test from 'node:test'
import assert from 'node:assert/strict'
import {meetingLeadMinutes,meetingCountdown,meetingStamp} from '../src/utils/meetingTime.js'
test('会议倒计时阈值和UTC+8输入',()=>{
 const start='2026-11-26T10:00:00+08:00'
 assert.equal(meetingStamp('2026-11-26 10:00:00'),'2026-11-26T10:00:00+08:00')
 for(const [minutes,lead] of [[30,10],[31,15],[60,15],[61,20]]){
  const end=new Date(Date.parse(start)+minutes*60000).toISOString()
  assert.equal(meetingLeadMinutes(start,end),lead)
  const meeting={start_at:start,end_at:end}
  assert.equal(meetingCountdown(meeting,Date.parse(start)-(lead+1)*60000),'')
  assert.match(meetingCountdown(meeting,Date.parse(start)-lead*60000),/距会议开始/)
  assert.equal(meetingCountdown(meeting,Date.parse(start)),'会议进行中')
  assert.equal(meetingCountdown(meeting,Date.parse(end)),'')
 }
})
