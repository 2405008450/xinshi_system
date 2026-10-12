import test from 'node:test'
import assert from 'node:assert/strict'
import { chatAvatarText, chatClock, chatDayKey, chatDateLabel, chatGroupStart } from '../src/utils/chatLayout.js'

test('聊天头像跳过全角标点，UTC+8 时间不依赖系统时区', () => {
  assert.equal(chatAvatarText('【标注】项目'), '标')
  assert.equal(chatAvatarText('（alice）'), 'A')
  assert.equal(chatAvatarText(''), '聊')
  for (const value of ['2026-10-09T09:18:43Z', '2026-10-09T17:18:43+08:00', '2026-10-09 17:18:43']) {
    assert.equal(chatClock(value), '17:18')
    assert.equal(chatDayKey(value), '2026-10-09')
    assert.equal(chatDateLabel(value, new Date('2026-10-09T10:00:00Z')), '17:18')
  }
  assert.equal(chatDateLabel('2026-10-08T23:59:00+08:00', new Date('2026-10-09T00:00:00+08:00')), '昨天')
  assert.equal(chatDateLabel('2025-10-09T00:00:00+08:00', new Date('2026-10-09T00:00:00+08:00')), '2025年10月9日')
  assert.equal(chatDateLabel('bad'), '')
})

test('连续消息只合并同发送人、同业务日期且相隔五分钟以内的有效消息', () => {
  const previous = { senderUserId: 'a', createdAt: '2026-10-09T09:00:00Z' }
  assert.equal(chatGroupStart({ ...previous, createdAt: '2026-10-09T17:05:00+08:00' }, previous), false)
  for (const message of [
    { ...previous, senderUserId: 'b' },
    { ...previous, createdAt: '2026-10-09T17:05:01+08:00' },
    { ...previous, createdAt: '2026-10-10T00:00:00+08:00' },
    { ...previous, createdAt: 'invalid' },
    { ...previous, recalledAt: '2026-10-09T17:01:00+08:00' },
  ]) assert.equal(chatGroupStart(message, previous), true)
  assert.equal(chatGroupStart(previous), true)
})
