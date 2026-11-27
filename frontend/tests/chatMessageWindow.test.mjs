import test from 'node:test'
import assert from 'node:assert/strict'
import { trimMessageWindow } from '../src/utils/chatMessageWindow.js'

test('trimMessageWindow 未超过上限时不裁剪', () => {
  const rows = Array.from({ length: 5 }, (_, i) => ({ id: String(i + 1), content: `m${i + 1}` }))
  const result = trimMessageWindow(rows, { maxReal: 5 })
  assert.equal(result.trimmed, false)
  assert.equal(result.messages.length, 5)
})

test('trimMessageWindow 超过上限时保留最新真实消息、全部乐观消息和受保护消息', () => {
  const rows = [
    ...Array.from({ length: 10 }, (_, i) => ({ id: String(i + 1), content: `m${i + 1}` })),
    { id: 'optimistic:cid-1', clientMessageId: 'cid-1', optimisticStatus: 'failed', content: '待重试' },
  ]
  const result = trimMessageWindow(rows, { maxReal: 4, protectedIds: ['2'] })
  assert.equal(result.trimmed, true)
  assert.deepEqual(
    result.messages.map(item => item.id),
    ['2', '7', '8', '9', '10', 'optimistic:cid-1'],
  )
})
