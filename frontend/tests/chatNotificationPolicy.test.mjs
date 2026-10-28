import test from 'node:test'
import assert from 'node:assert/strict'
import { createChatNotificationFeed, isVisibleConversation } from '../src/utils/chatNotificationPolicy.js'

const message = (id, minute, type = 'direct_chat') => ({ id, notification_type: type, created_at: `2026-10-28T10:${minute}:00+08:00` })

test('首次普通历史不弹，重连补齐新消息并与实时去重，同一时间的不同消息不丢失', () => {
  const feed = createChatNotificationFeed()
  assert.deepEqual(feed.consume([message('old', '00'), message('mention', '00', 'direct_chat_mention')]).map(i => i.id), ['mention'])
  feed.remember('socket')
  assert.deepEqual(feed.consume([message('new', '02'), message('socket', '01'), message('old', '00')]).map(i => i.id), ['new'])
  assert.deepEqual(feed.consume([message('same-time', '02'), message('new', '02')]).map(i => i.id), ['same-time'])
  assert.deepEqual(feed.consume([message('old', '00')]), [])
})

test('只有页面前台、获得焦点且对应会话可见时抑制普通提醒', () => {
  const notification = { related_project_type: 'direct', related_entity_id: 'pair' }
  const state = { windows: [{ projectType: 'direct', projectId: 'pair', minimized: false }] }
  const document = { visibilityState: 'visible', hasFocus: () => true }
  const visible = item => !item.minimized
  assert.equal(isVisibleConversation(notification, state, visible, document), true)
  state.windows[0].minimized = true
  assert.equal(isVisibleConversation(notification, state, visible, document), false)
  state.windows[0].minimized = false
  document.visibilityState = 'hidden'
  assert.equal(isVisibleConversation(notification, state, visible, document), false)
  document.visibilityState = 'visible'; document.hasFocus = () => false
  assert.equal(isVisibleConversation(notification, state, visible, document), false)
  document.hasFocus = () => true
  assert.equal(isVisibleConversation({ ...notification, related_entity_id: 'other' }, state, visible, document), false)
})
