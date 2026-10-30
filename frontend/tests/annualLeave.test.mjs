import test from 'node:test'
import assert from 'node:assert/strict'
import {annualLeaveDays,annualLeaveGrantDate,nextAnnualLeaveIncrease} from '../src/utils/annualLeave.js'
test('首年6月30日含当天，下半年入职次年元旦获1天，此后各周年后三个月增长',()=>{
  assert.equal(annualLeaveDays('2026-06-30','2026-10-28'),1)
  assert.equal(annualLeaveDays('2026-07-01','2026-10-28'),0)
  assert.equal(annualLeaveDays('2025-07-01','2026-01-01'),1)
  assert.equal(annualLeaveDays('2025-06-30','2026-09-29'),1)
  assert.equal(annualLeaveDays('2025-06-30','2026-09-30'),2)
  assert.equal(annualLeaveDays('2025-07-01','2026-10-01'),2)
  assert.equal(annualLeaveDays('2024-09-09','2024-12-31'),0)
  assert.equal(nextAnnualLeaveIncrease('2024-09-09','2024-12-31'),'2025-01-01')
  assert.equal(annualLeaveDays('2024-09-09','2025-01-01'),1)
  assert.equal(nextAnnualLeaveIncrease('2024-09-09','2025-01-01'),'2025-12-09')
  assert.equal(annualLeaveDays('2024-09-09','2026-01-01'),2)
  assert.deepEqual(['2024-09-09','2025-05-07','2026-01-12'].map(hire=>annualLeaveDays(hire,'2026-10-30')),[2,2,1])
})
test('月底、闰日、未来入职、缺失日期与10天上限',()=>{
  assert.equal(annualLeaveGrantDate('2025-03-31',1),'2026-06-30')
  assert.equal(annualLeaveGrantDate('2024-02-29',1),'2025-05-28')
  assert.equal(annualLeaveDays(null,'2026-10-28'),null)
  assert.equal(annualLeaveDays('2027-01-01','2026-10-28'),0)
  assert.equal(annualLeaveDays('2010-01-01','2026-10-28'),10)
  assert.equal(nextAnnualLeaveIncrease('2010-01-01','2026-10-28'),null)
  assert.equal(nextAnnualLeaveIncrease('2025-06-30','2026-09-30'),'2027-09-30')
})
