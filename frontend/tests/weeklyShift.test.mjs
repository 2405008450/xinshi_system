import test from 'node:test'
import assert from 'node:assert/strict'
import {currentShiftWeek,shiftWeek,shiftWeekEnd,shiftMonthWeeks} from '../src/utils/monthlyShift.js'
test('本周按香港日历周计算，周一至周日，跨月跨年保持一周',()=>{
 assert.equal(currentShiftWeek(new Date('2026-10-25T20:00:00Z')),'2026-10-26')
 assert.equal(currentShiftWeek(new Date('2026-10-25T06:00:00+08:00')),'2026-10-19')
 assert.equal(shiftWeek('2026-11-01'),'2026-10-26');assert.equal(shiftWeekEnd('2026-11-01'),'2026-11-01')
 assert.equal(shiftWeek('2027-01-01'),'2026-12-28');assert.equal(shiftWeekEnd('2027-01-01'),'2027-01-03')
})
test('本周、上周、下周快捷日期分别相差七天',()=>{
 assert.equal(shiftWeek('2026-10-25',-1),'2026-10-12')
 assert.equal(shiftWeek('2026-10-25',0),'2026-10-19')
 assert.equal(shiftWeek('2026-10-25',1),'2026-10-26')
})

test('月份包含全部相交自然周，跨月边界共用周键，不使用整月相同安排',()=>{
 assert.deepEqual(shiftMonthWeeks('2026-10'),['2026-09-28','2026-10-05','2026-10-12','2026-10-19','2026-10-26'])
 assert.equal(shiftMonthWeeks('2026-11')[0],'2026-10-26')
 assert.equal(shiftMonthWeeks('2027-01')[0],'2026-12-28')
 assert.equal(shiftMonthWeeks('2026-03').length,6)
 assert.equal(shiftMonthWeeks('2021-02').length,4)
})
