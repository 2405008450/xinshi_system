import test from 'node:test'
import assert from 'node:assert/strict'
import { annotationStatusLabels, annotationStatusLabel, annotationStatusType, annotationStatusSummary, convertAnnotationKeys } from '../src/utils/annotationStatus.js'

test('所有标注状态兼容原始枚举和旧驼峰缓存，保持相同中文和颜色', () => {
  for (const [status, label] of Object.entries(annotationStatusLabels)) {
    const camel = status.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
    assert.equal(annotationStatusLabel(status), label)
    assert.equal(annotationStatusLabel(camel), label)
    assert.equal(annotationStatusType(camel), annotationStatusType(status))
  }
  assert.equal(annotationStatusLabel('future_status'), '未知状态')
})
test('分页和详情响应转换保留状态统计的业务键', () => {
  const converted = convertAnnotationKeys({ items: [{ project_status: 'trial_preparation', child_status_counts: { trial_preparation: 7 } }] }, value => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()))
  assert.deepEqual(converted.items[0], { projectStatus: 'trial_preparation', childStatusCounts: { trial_preparation: 7 } })
  assert.deepEqual(annotationStatusSummary(converted.items[0].childStatusCounts), [{ status: 'trial_preparation', count: 7, label: '试标准备' }])
})
test('混用统计键合并为一条中文标签，零数量不展示', () => {
  assert.deepEqual(annotationStatusSummary({ trial_preparation: 2, trialPreparation: 5, ended: 0 }), [{ status: 'trial_preparation', count: 7, label: '试标准备' }])
})
