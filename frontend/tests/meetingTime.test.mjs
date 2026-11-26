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
  assert.match(meetingCountdown(meeting,Date.parse(start)-lead*60000),/会议即将开始/)
  assert.equal(meetingCountdown(meeting,Date.parse(start)),'已到计划开始时间，等待召开人开始')
  assert.equal(meetingCountdown(meeting,Date.parse(end)),'')
 }
})

test('会议倒计时由手动进行中的服务器时刻启动，超时仍需人工结束',()=>{
 const meeting={start_at:'2026-11-26T10:00:00+08:00',end_at:'2026-11-26T10:30:00+08:00',status:'in_progress',status_started_at:'2026-11-26T11:00:00+08:00'}
 assert.equal(meetingCountdown(meeting,Date.parse('2026-11-26T11:00:00+08:00')),'会议剩余 30分00秒')
 assert.equal(meetingCountdown(meeting,Date.parse('2026-11-26T11:31:00+08:00')),'会议已超时 1分00秒')
 for(const status of ['ended','cancelled'])assert.equal(meetingCountdown({...meeting,status},Date.parse(meeting.status_started_at)),'')
})
