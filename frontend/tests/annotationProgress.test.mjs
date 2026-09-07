import test from 'node:test'
import assert from 'node:assert/strict'

import { groupAnnotationProgressRows } from '../src/utils/annotationProgress.js'

const row = (id, fromStatus, toStatus, effectiveOn, changeNote, changedAt = `${effectiveOn}T10:00:00`) => ({
  id,
  fromStatus,
  toStatus,
  effectiveOn,
  changedAt,
  changedByName: '测试用户',
  changeNote,
})

test('具体进度缩进归入对应状态阶段，状态变更说明也作为子节点', () => {
  const groups = groupAnnotationProgressRows([
    row('progress', 'trial_in_progress', 'trial_in_progress', '2026-09-02', '一个语种找不到人'),
    row('stage', 'trial_preparation', 'trial_in_progress', '2026-09-01', '客户确认开始试标'),
  ], 'trial_in_progress')

  assert.equal(groups.length, 1)
  assert.equal(groups[0].status, 'trial_in_progress')
  assert.equal(groups[0].isCurrent, true)
  assert.deepEqual(groups[0].children.map((item) => item.kind), ['progress', 'status-note'])
})

test('状态重复出现时按节点日期归入最近一次对应状态阶段', () => {
  const groups = groupAnnotationProgressRows([
    row('progress-new', 'trial_in_progress', 'trial_in_progress', '2026-09-06', '第二轮试标进展'),
    row('stage-new', 'trial_preparation', 'trial_in_progress', '2026-09-05', null),
    row('stage-middle', 'trial_in_progress', 'trial_failed', '2026-09-03', null),
    row('progress-old', 'trial_in_progress', 'trial_in_progress', '2026-09-02', '第一轮试标进展'),
    row('stage-old', 'trial_preparation', 'trial_in_progress', '2026-09-01', null),
  ], 'trial_in_progress')

  const repeatedStages = groups.filter((group) => group.status === 'trial_in_progress')
  assert.equal(repeatedStages.length, 2)
  assert.deepEqual(repeatedStages[0].children.map((item) => item.id), ['progress-new'])
  assert.deepEqual(repeatedStages[1].children.map((item) => item.id), ['progress-old'])
})

test('同日记录按录入时间倒序，缺少状态节点时建立兼容分组', () => {
  const groups = groupAnnotationProgressRows([
    row('early', 'resource_sourcing', 'resource_sourcing', '2026-08-20', '上午进度', '2026-09-07T09:00:00'),
    row('late', 'resource_sourcing', 'resource_sourcing', '2026-08-20', '下午进度', '2026-09-07T15:00:00'),
  ], 'project_in_progress')

  assert.equal(groups.length, 1)
  assert.equal(groups[0].synthetic, true)
  assert.deepEqual(groups[0].children.map((item) => item.id), ['late', 'early'])
})
