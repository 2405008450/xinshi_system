import assert from 'node:assert/strict'
import test from 'node:test'
import { CHAT_MEMBERS_REFRESH_MS, CHAT_WINDOW_REFRESH_MS, createChatWindowFreshness } from '../src/utils/chatWindowFreshness.js'

test('连续切换时复用刚读取的会话数据，成员和消息独立过期', () => {
  let time = 0
  const messages = createChatWindowFreshness(CHAT_WINDOW_REFRESH_MS, () => time)
  const members = createChatWindowFreshness(CHAT_MEMBERS_REFRESH_MS, () => time)
  assert.equal(messages.isStale(), true)
  messages.begin()()
  members.begin()()
  time = CHAT_WINDOW_REFRESH_MS - 1
  assert.equal(messages.isStale(), false)
  assert.equal(members.isStale(), false)
  time = CHAT_WINDOW_REFRESH_MS
  assert.equal(messages.isStale(), true)
  assert.equal(members.isStale(), false)
  time = CHAT_MEMBERS_REFRESH_MS
  assert.equal(members.isStale(), true)
})

test('参与人变更和重连都能让在途旧响应失效', () => {
  const freshness = createChatWindowFreshness(CHAT_MEMBERS_REFRESH_MS, () => 0)
  const obsolete = freshness.begin()
  freshness.invalidate()
  obsolete()
  assert.equal(freshness.isStale(), true)
  freshness.begin()()
  assert.equal(freshness.isStale(), false)
})
