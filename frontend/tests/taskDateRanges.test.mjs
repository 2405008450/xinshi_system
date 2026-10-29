import test from 'node:test'
import assert from 'node:assert/strict'
import {arrangementDateRange} from '../src/utils/taskDateRanges.js'
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
