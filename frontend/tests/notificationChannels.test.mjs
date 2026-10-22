import test from 'node:test'
import assert from 'node:assert/strict'
import { CHAT_NOTIFICATION_TYPES, isBusinessNotification, isChatNotification, isChatMentionNotification, isChatAttentionNotification } from '../src/utils/notificationChannels.js'

test('群聊、私聊、提及与邀请均进入聊天，交接与未知业务类型留在通知', () => {
  for (const type of CHAT_NOTIFICATION_TYPES) {
    assert.equal(isChatNotification({ notification_type: type }), true)
    assert.equal(isBusinessNotification({ notification_type: type }), false)
    assert.equal(isChatMentionNotification({ notification_type: type }), type.endsWith('_mention'))
  }
  for (const type of ['workflow_handover_pending', 'project_manager_handover_accepted', 'workflow_delegation_overdue', 'future_business_event', '']) {
    assert.equal(isBusinessNotification({ notification_type: type }), true)
    assert.equal(isChatNotification({ notification_type: type }), false)
    assert.equal(isChatMentionNotification({ notification_type: type }), false)
  }
})


test('普通聊天不弹窗或桌面提醒，@提及和邀请保留主动提醒', () => {
  for (const type of ['project_chat','direct_chat']) assert.equal(isChatAttentionNotification({notification_type:type}),false)
  for (const type of ['project_chat_mention','annotation_project_chat_mention','direct_chat_mention','annotation_project_chat_invite','direct_chat_invite']) assert.equal(isChatAttentionNotification({notification_type:type}),true)
  assert.equal(isChatAttentionNotification({notification_type:'workflow_handover_pending'}),false)
})
