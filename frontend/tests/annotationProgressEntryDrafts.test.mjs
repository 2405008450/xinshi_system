import assert from 'node:assert/strict'
import test from 'node:test'
import { useAnnotationProgressEntryDrafts } from '../src/composables/useAnnotationProgressEntryDrafts.js'

const create = () => useAnnotationProgressEntryDrafts({ now: () => '2026-10-17 17:05:00' })

test('补充进度与状态变更往返切换保留各自文本、时间、目标和来源', () => {
  const entry = create()
  entry.reset('trial_submitted')
  Object.assign(entry.form.value, { projectStatus: 'trial_preparation', effectiveOn: '2026-10-16 18:00:00', changeNote: '寻找德语人员' })
  entry.stageKey.value = 'historical-stage'
  entry.source.value = { messageCount: 2, senderSummary: '黄萌' }
  entry.mode.value = 'status'
  assert.equal(entry.form.value.changeNote, '')
  Object.assign(entry.form.value, { projectStatus: 'project_in_progress', changeNote: '客户确认开始执行' })
  entry.mode.value = 'progress'
  assert.deepEqual({ ...entry.form.value }, { projectStatus: 'trial_preparation', effectiveOn: '2026-10-16 18:00:00', changeNote: '寻找德语人员' })
  assert.equal(entry.stageKey.value, 'historical-stage')
  assert.equal(entry.source.value.messageCount, 2)
  entry.mode.value = 'status'
  assert.equal(entry.form.value.changeNote, '客户确认开始执行')
  assert.equal(entry.source.value, null)
})

test('清理提交成功的草稿不影响另一模式，隐藏草稿仍可被关闭检查发现', () => {
  const entry = create()
  entry.reset('trial_submitted')
  entry.form.value.changeNote = '补充草稿'
  entry.mode.value = 'status'
  entry.form.value.projectStatus = 'project_in_progress'
  entry.clear('status')
  assert.equal(entry.hasDraft('status'), false)
  assert.equal(entry.hasDraft('progress'), true)
  assert.equal(entry.drafts.progress.form.changeNote, '补充草稿')
})

test('仅修改时间或所属状态也标记为未保存，恢复初值后取消标记', () => {
  const entry = create()
  entry.reset('trial_submitted')
  assert.equal(entry.hasDraft('progress'), false)
  entry.form.value.effectiveOn = '2026-10-16 18:00:00'
  assert.equal(entry.hasDraft('progress'), true)
  entry.form.value.effectiveOn = '2026-10-17 17:05:00'
  assert.equal(entry.hasDraft('progress'), false)
  entry.form.value.projectStatus = 'trial_preparation'
  assert.equal(entry.hasDraft('progress'), true)
})

test('详情晚到只修正默认状态，保留正在填写的正文及选中的历史节点', () => {
  const entry = create()
  entry.form.value.changeNote = '加载期间开始填写'
  entry.setInitialProjectStatus('trial_submitted')
  assert.equal(entry.form.value.projectStatus, 'trial_submitted')
  assert.equal(entry.form.value.changeNote, '加载期间开始填写')
  entry.form.value.projectStatus = 'trial_preparation'
  entry.stageKey.value = 'historical-stage'
  entry.setInitialProjectStatus('project_in_progress')
  assert.equal(entry.form.value.projectStatus, 'trial_preparation')
})

test('关闭后重新打开清理全部项目草稿、来源和节点选择', () => {
  const entry = create()
  entry.form.value.changeNote = '旧内容'
  entry.source.value = { messageCount: 1 }
  entry.stageKey.value = 'old-stage'
  entry.mode.value = 'status'
  entry.form.value.changeNote = '旧说明'
  entry.reset('trial_preparation')
  assert.equal(entry.mode.value, 'progress')
  for (const mode of ['progress', 'status']) {
    assert.equal(entry.hasDraft(mode), false)
    assert.equal(entry.drafts[mode].form.changeNote, '')
    assert.equal(entry.drafts[mode].source, null)
    assert.equal(entry.drafts[mode].stageKey, '')
  }
})
