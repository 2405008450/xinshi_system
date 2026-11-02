import test from 'node:test'
import assert from 'node:assert/strict'
import {requiresDinnerConfirmation} from '../src/utils/attendanceDinner.js'
test('UTC+8原考勤日18:50严格边界及跨日、补卡时间',()=>{
  assert.equal(requiresDinnerConfirmation('2026-11-02','2026-11-02T18:50:00'),false)
  assert.equal(requiresDinnerConfirmation('2026-11-02','2026-11-02T18:50:01'),true)
  assert.equal(requiresDinnerConfirmation('2026-11-02','2026-11-02T10:50:00Z'),false)
  assert.equal(requiresDinnerConfirmation('2026-11-02','2026-11-03T02:00:00+08:00'),true)
  assert.equal(requiresDinnerConfirmation('2026-11-02',null),false)
})
