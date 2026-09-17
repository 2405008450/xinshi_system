import test from 'node:test'
import assert from 'node:assert/strict'

import { groupProjectProgressRows } from '../src/utils/annotationProgress.js'

test('口译进度按状态节点组成时间线并标记当前状态', () => {
  const groups = groupProjectProgressRows([
    { id: '3', fromStatus: 'deal_pending_execution', toStatus: 'deal_pending_execution', effectiveOn: '2026-09-16T15:00:00', changedAt: '2026-09-16T15:01:00', changeNote: '译员与场地均已确认' },
    { id: '2', fromStatus: 'initial_follow_up', toStatus: 'deal_pending_execution', effectiveOn: '2026-09-16T14:00:00', changedAt: '2026-09-16T14:01:00', changeNote: '客户确认成交' },
    { id: '1', fromStatus: null, toStatus: 'initial_follow_up', effectiveOn: '2026-09-15T09:00:00', changedAt: '2026-09-15T09:00:00', changeNote: null },
  ], 'deal_pending_execution')

  assert.equal(groups.length, 2)
  assert.equal(groups[0].status, 'deal_pending_execution')
  assert.equal(groups[0].isCurrent, true)
  assert.deepEqual(groups[0].children.map((item) => item.changeNote), [
    '译员与场地均已确认',
    '客户确认成交',
  ])
})
