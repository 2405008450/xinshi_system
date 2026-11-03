import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  switchConsultationIntake,
  normalizeConsultationIntakePriority,
  interpretationDirectionsError,
  interpretationTimeRangesError,
} from '../src/utils/consultationIntakeValidation.js'

const emptyIntake = () => ({ customer_deadline_time: '', language_directions: [], service_content: '' })

test('切换咨询类型再返回时保留交稿时间，并隔离其他类型的数据', () => {
  const form = { project_intake: { ...emptyIntake(), customer_deadline_time: '2026-11-20T18:30:00', service_content: '翻译' } }
  switchConsultationIntake(form, 'translation', '口译项目', emptyIntake)
  assert.equal(form.project_intake.customer_deadline_time, '')
  form.project_intake.language_directions.push({ source_language_id: 'zh', target_language_id: 'en', required_count: 2 })
  switchConsultationIntake(form, '口译项目', 'translation', emptyIntake)
  assert.equal(form.project_intake.customer_deadline_time, '2026-11-20T18:30:00')
  assert.equal(form.project_intake.service_content, '翻译')
  assert.deepEqual(form.project_intake.language_directions, [])
  switchConsultationIntake(form, 'translation', '口译项目', emptyIntake)
  assert.equal(form.project_intake.language_directions[0].required_count, 2)
  form.project_intake.language_directions[0].required_count = 3
  assert.equal(form.project_intake_drafts['口译项目'].language_directions[0].required_count, 2)
})

test('同类咨询重复选择不重置；主动清空的日期不会被旧缓存恢复', () => {
  const form = { project_intake: { ...emptyIntake(), customer_deadline_time: '2026-11-20T18:30:00' } }
  const original = form.project_intake
  switchConsultationIntake(form, 'translation', 'translation', emptyIntake)
  assert.equal(form.project_intake, original)
  switchConsultationIntake(form, 'translation', '简单咨询', emptyIntake)
  switchConsultationIntake(form, '简单咨询', 'translation', emptyIntake)
  form.project_intake.customer_deadline_time = null
  switchConsultationIntake(form, 'translation', '简单咨询', emptyIntake)
  switchConsultationIntake(form, '简单咨询', 'translation', emptyIntake)
  assert.equal(form.project_intake.customer_deadline_time, null)
})

test('表单草稿序列化恢复后仍可找回切换前的时间', () => {
  let form = { project_intake: { ...emptyIntake(), customer_deadline_time: '2026-11-20T18:30:00' } }
  switchConsultationIntake(form, 'translation', '口译项目', emptyIntake)
  form = JSON.parse(JSON.stringify(form))
  switchConsultationIntake(form, '口译项目', 'translation', emptyIntake)
  assert.equal(form.project_intake.customer_deadline_time, '2026-11-20T18:30:00')
})

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
