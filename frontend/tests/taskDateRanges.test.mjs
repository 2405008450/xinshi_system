import test from 'node:test'
import assert from 'node:assert/strict'
import {arrangementDateRange,receivedReportDateRange,defaultReceivedReportDateRange} from '../src/utils/taskDateRanges.js'

test('报告默认日期以UTC+8的18点为界，昨日始终为自然日',()=>{
 for(const [instant,day] of [
  ['2026-11-27T00:00:00+08:00','2026-11-26'],
  ['2026-11-27T17:59:59+08:00','2026-11-26'],
  ['2026-11-27T18:00:00+08:00','2026-11-27'],
  ['2026-11-27T23:59:59+08:00','2026-11-27'],
  ['2026-11-28T00:00:00+08:00','2026-11-27'],
  ['2027-01-01T00:00:00+08:00','2026-12-31'],
 ])assert.deepEqual(defaultReceivedReportDateRange(instant),[day,day])
 assert.deepEqual(receivedReportDateRange('today','2026-11-27'),['2026-11-27','2026-11-27'])
})

test('报告快捷日期支持前三天、上个完整自然周、上个自然月及全部日期',()=>{
 assert.deepEqual(receivedReportDateRange('yesterday','2026-11-27'),['2026-11-26','2026-11-26'])
 assert.deepEqual(receivedReportDateRange('before-yesterday','2026-11-27'),['2026-11-25','2026-11-25'])
 assert.deepEqual(receivedReportDateRange('three-days-ago','2026-11-27'),['2026-11-24','2026-11-24'])
 assert.deepEqual(receivedReportDateRange('last-week','2026-11-27'),['2026-11-16','2026-11-22'])
 assert.deepEqual(receivedReportDateRange('last-month','2026-11-27'),['2026-10-01','2026-10-31'])
 assert.deepEqual(receivedReportDateRange('all','2026-11-27'),[])
 assert.deepEqual(receivedReportDateRange('last-month','2026-01-01'),['2025-12-01','2025-12-31'])
 assert.deepEqual(receivedReportDateRange('last-month','2024-03-01'),['2024-02-01','2024-02-29'])
})

test('报告查看的昨天按UTC+8自然日计算，凌晨不多退一天',()=>{
 const original=Date.now
 try{Date.now=()=>Date.parse('2026-11-26T18:00:00Z');assert.deepEqual(receivedReportDateRange('yesterday'),['2026-11-26','2026-11-26'])}finally{Date.now=original}
})
test('历史安排快捷日期按完整自然周查询',()=>{
  assert.equal(arrangementDateRange('today','2026-10-25'),null)
  assert.deepEqual(arrangementDateRange('yesterday','2026-10-25'),['2026-10-24','2026-10-24'])
  assert.deepEqual(arrangementDateRange('before-yesterday','2026-10-25'),['2026-10-23','2026-10-23'])
  assert.deepEqual(arrangementDateRange('last-week','2026-10-25'),['2026-10-12','2026-10-18'])
  assert.deepEqual(arrangementDateRange('previous-week','2026-10-25'),['2026-10-05','2026-10-11'])
})
test('自然周支持跨年且不依赖浏览器默认时区',()=>{
  assert.deepEqual(arrangementDateRange('last-week','2026-01-01'),['2025-12-22','2025-12-28'])
  assert.deepEqual(arrangementDateRange('before-yesterday','2026-01-01'),['2025-12-30','2025-12-30'])
})
