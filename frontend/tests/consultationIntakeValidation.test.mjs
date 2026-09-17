import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  interpretationDirectionsError,
  interpretationTimeRangesError,
} from '../src/utils/consultationIntakeValidation.js'

const consultationPage = readFileSync(
  new URL('../src/views/client/Consultations.vue', import.meta.url),
  'utf8',
)

test('口译预定结束时间不能早于开始时间', () => {
  assert.equal(interpretationTimeRangesError([{
    scheduled_start: '2026-10-21T00:00:00',
    scheduled_end: '2026-09-27T00:00:00',
  }]), '预定结束时间不能早于预定开始时间')
  assert.equal(interpretationTimeRangesError([{
    scheduled_start: '2026-09-27T00:00:00',
    scheduled_end: '2026-10-21T00:00:00',
  }]), '')
})

test('口译方向拒绝相同语种和重复双向组合', () => {
  assert.equal(interpretationDirectionsError([{
    source_language_id: 'zh', target_language_id: 'zh', required_count: 1,
  }]), '同一口译方向内的语种不能重复')
  assert.equal(interpretationDirectionsError([
    { source_language_id: 'zh', target_language_id: 'en', required_count: 1 },
    { source_language_id: 'en', target_language_id: 'zh', required_count: 1 },
  ]), '同一双向口译方向不能重复')
})

test('用户调整口译预定时间后立即触发表单校验', () => {
  assert.match(consultationPage, /@update:model-value="\(value\) => handleInterpretationTimeRangeChange\(index, 'scheduled_start', value\)"/)
  assert.match(consultationPage, /@update:model-value="\(value\) => handleInterpretationTimeRangeChange\(index, 'scheduled_end', value\)"/)
  assert.match(consultationPage, /validateField\('project_intake\.time_ranges'\)/)
})
