import test from 'node:test'
import assert from 'node:assert/strict'
import { chatAvatarText, chatClock, chatDayKey, chatDateLabel, chatMessageTime, chatGroupStart } from '../src/utils/chatLayout.js'

test('每条留言时间显示完整日期、时分秒，今天昨天按UTC+8自然日判断', () => {
  const now = new Date('2026-10-21T08:00:00Z')
  for (const value of ['2026-10-21T09:18:43Z', '2026-10-21T17:18:43+08:00', '2026-10-21 17:18:43']) {
    assert.equal(chatMessageTime(value, now), '今天（2026年10月21日） 17:18:43')
  }
  assert.equal(chatMessageTime('2026-10-20T23:59:07+08:00', now), '昨天（2026年10月20日） 23:59:07')
  assert.equal(chatMessageTime('2025-10-21T00:00:05+08:00', now), '2025年10月21日 00:00:05')
  assert.equal(chatMessageTime('2026-10-22T01:02:03+08:00', now), '2026年10月22日 01:02:03')
  assert.equal(chatMessageTime('bad', now), '-')
  assert.equal(chatMessageTime(null, now), '-')
})

test('跨年及UTC日期不同的时间仍按UTC+8判断今天与昨天，不重复加八小时', () => {
  const now = new Date('2026-12-31T16:00:00Z')
  assert.equal(chatMessageTime('2026-12-31T16:00:00Z', now), '今天（2027年01月01日） 00:00:00')
  assert.equal(chatMessageTime('2026-12-31T15:59:59Z', now), '昨天（2026年12月31日） 23:59:59')
  assert.equal(chatMessageTime('2027-01-01T00:00:00', now), '今天（2027年01月01日） 00:00:00')
})

test('时间显示设置支持隐藏、去掉年份和只显示时分秒，保留今天昨天语义', () => {
  const now = new Date('2026-10-21T08:00:00Z')
  assert.equal(chatMessageTime('2026-10-21T17:18:43+08:00', now, 'hidden'), '')
  assert.equal(chatMessageTime('2026-10-21T17:18:43+08:00', now, 'no-year'), '今天（10月21日） 17:18:43')
  assert.equal(chatMessageTime('2026-10-20T17:18:43+08:00', now, 'no-year'), '昨天（10月20日） 17:18:43')
  assert.equal(chatMessageTime('2025-10-09T17:18:43+08:00', now, 'no-year'), '10月09日 17:18:43')
  assert.equal(chatMessageTime('2026-10-21T17:18:43+08:00', now, 'time'), '17:18:43')
})

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
