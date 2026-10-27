import test from 'node:test'
import assert from 'node:assert/strict'
import { compareMentionSessions, latestMentionAt } from '../src/utils/chatMentionSort.js'

const rows = [
  { key: 'read-new', customerName: 'A', mentionUnread: 0, latestMentionAt: '2026-10-27T18:00:00+08:00' },
  { key: 'unread-old', customerName: 'B', mentionUnread: 2, latestMentionAt: '2026-10-26T09:00:00+08:00', lastMessage: { createdAt: '2026-10-28T10:00:00+08:00' } },
  { key: 'unread-new', customerName: 'A', mentionUnread: 1, latestMentionAt: '2026-10-27T09:00:00+08:00' },
]
test('未读优先，默认按实际提及时间倒序，普通新消息不影响顺序', () => {
  assert.deepEqual([...rows].sort(compareMentionSessions).map(r => r.key), ['unread-new', 'unread-old', 'read-new'])
})
test('时间升序和客户升降序始终保留未读优先', () => {
  for (const [sort, expected] of [
    ['time_asc', ['unread-old', 'unread-new', 'read-new']],
    ['customer_asc', ['unread-new', 'unread-old', 'read-new']],
    ['customer_desc', ['unread-old', 'unread-new', 'read-new']],
  ]) assert.deepEqual([...rows].sort((a,b) => compareMentionSessions(a,b,sort)).map(r => r.key), expected)
})
test('合并主子订单使用整个订单系列中最新的提及时间；无客户放最后', () => {
  assert.equal(latestMentionAt({ variants: rows }), rows[0].latestMentionAt)
  for (const sort of ['customer_asc','customer_desc']) assert.ok(compareMentionSessions({key:'a',customerName:'A'}, {key:'b'}, sort) < 0)
})
