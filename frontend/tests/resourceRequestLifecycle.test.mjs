import assert from 'node:assert/strict'
import test from 'node:test'
import { canPauseDemand, canSendDemand, demandStatusText } from '../src/utils/resourceRequestLifecycle.js'

test('草稿、取消、完成与暂停需求不能再次暂停；暂停不能通过发送恢复', () => {
  const active = { id: 'r', demandStatus: 'confirmed', requestStatus: 'in_progress', progressPercent: 35 }
  assert.equal(canPauseDemand(active), true)
  for (const change of [{ id: '' }, { demandStatus: 'draft' }, { demandStatus: 'cancelled' }, { demandStatus: 'paused' }, { requestStatus: 'fulfilled' }, { requestStatus: 'cancelled' }, { progressPercent: 100 }]) {
    assert.equal(canPauseDemand({ ...active, ...change }), false)
  }
  assert.equal(canSendDemand({ demandStatus: 'paused' }), false)
  assert.equal(canSendDemand({ demandStatus: 'confirmed' }), false)
  assert.equal(canSendDemand({ demandStatus: 'draft' }), true)
  assert.equal(canSendDemand({ demandStatus: 'cancelled' }), true)
  assert.equal(demandStatusText('paused'), '需求已暂停')
})
