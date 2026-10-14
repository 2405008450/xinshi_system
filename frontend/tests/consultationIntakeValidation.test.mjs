import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  normalizeConsultationIntakePriority,
  interpretationDirectionsError,
  interpretationTimeRangesError,
} from '../src/utils/consultationIntakeValidation.js'

const consultationPage = readFileSync(
  new URL('../src/views/client/Consultations.vue', import.meta.url),
  'utf8',
)

test('标注咨询新增及旧草稿的空优先级不提交，且不修改原表单', () => {
  for (const type of ['标注项目', 'annotation']) {
    for (const priority of ['', '  ', null, undefined]) {
      const intake = { priority, task_description: '测试标注任务' }
      const normalized = normalizeConsultationIntakePriority(intake, type)
      assert.equal(Object.hasOwn(normalized, 'priority'), false)
      assert.equal(normalized.task_description, intake.task_description)
      assert.equal(Object.hasOwn(intake, 'priority'), true)
      assert.equal(intake.priority, priority)
    }
  }
})

test('保留标注咨询显式优先级及笔译优先级的原有语义', () => {
  for (const priority of ['low', 'medium', 'high', 'urgent']) {
    assert.equal(normalizeConsultationIntakePriority({ priority }, '标注项目').priority, priority)
  }
  for (const priority of ['', '低', '中', '高', '紧急']) {
    assert.equal(normalizeConsultationIntakePriority({ priority }, '笔译项目').priority, priority)
  }
})

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
