import test from 'node:test'
import assert from 'node:assert/strict'
import {DEFAULT_ARRANGEMENT_EXCLUSIONS,arrangementDeadlineShortcut,withArrangementExclusions} from '../src/utils/arrangementFilters.js'
test('默认排除五个状态，已安排可以独立追加，空选不产生排除条件',()=>{
 assert.deepEqual(DEFAULT_ARRANGEMENT_EXCLUSIONS,['pending_confirmation','sent_to_client','feedback_sent_to_client','paused','cancelled'])
 assert.equal(withArrangementExclusions(undefined,[]),undefined)
 const existing={customer_reception_time:{op:'between',from:'2026-10-01',to:'2026-10-25'}}
 const result=JSON.parse(withArrangementExclusions(JSON.stringify(existing),['arranged']))
 assert.deepEqual(result,{...existing,excluded_project_status:{op:'in',value:['arranged']}})
})
test('UTC+8 零点到七点之前确认，七点无需确认；日历日期独立于日报换日',()=>{
 for(const hour of ['00:00:00','06:59:59']){
  const value=arrangementDeadlineShortcut('today',new Date(`2026-10-25T${hour}+08:00`))
  assert.deepEqual(value.range,['2026-10-25','2026-10-25']);assert.equal(value.needsConfirmation,true)
 }
 assert.equal(arrangementDeadlineShortcut('today',new Date('2026-10-25T07:00:00+08:00')).needsConfirmation,false)
 assert.deepEqual(arrangementDeadlineShortcut('tomorrow',new Date('2026-12-31T20:00:00Z')).range,['','2027-01-02'])
 assert.deepEqual(arrangementDeadlineShortcut('tomorrow',new Date('2026-10-31T23:59:59+08:00')).range,['','2026-11-01'])
})
