import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(new URL('../src/views/project/AnnotationTrials.vue', import.meta.url), 'utf8')
const model = fs.readFileSync(new URL('../../annotation_ops_models.py', import.meta.url), 'utf8')
const migration = fs.readFileSync(new URL('../../data/migrations/20261010_expand_annotation_trial_workspace.sql', import.meta.url), 'utf8')

test('试标流程提供项目级管理窗口、人数策略和最大化能力', () => {
  assert.match(page, /试标\/试采管理/)
  assert.match(page, /workspaceMaximized/)
  assert.match(page, /编辑人数策略/)
  assert.match(page, /建议联系/)
  assert.match(page, /人才概览储备/)
})

test('候选编辑表单支持一人多岗所需的独立维度与三段时间', () => {
  assert.match(page, /form\.activityType/)
  assert.match(page, /form\.dutyRole/)
  assert.match(page, /form\.languageItemId/)
  assert.match(page, /form\.startedAt/)
  assert.match(page, /form\.deadlineAt/)
  assert.match(page, /form\.submittedAt/)
  assert.match(model, /uq_annotation_trial_business_identity/)
})

test('试标工作台迁移保留项目级自定义字段并增加跟进时间线', () => {
  assert.match(page, /table-code="trial"/)
  assert.match(page, /AnnotationCustomFieldInputs/)
  assert.match(page, /跟进记录/)
  assert.match(migration, /annotation_trial_follow_up/)
  assert.match(migration, /annotation_trial_strategy/)
})
