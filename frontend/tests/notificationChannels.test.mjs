import test from 'node:test'
import assert from 'node:assert/strict'
import { CHAT_NOTIFICATION_TYPES, isBusinessNotification, isChatNotification, isChatMentionNotification, isChatAttentionNotification, isDesktopAttentionNotification, isSystemNotification, CONVERSATION_NOTIFICATION_TYPES } from '../src/utils/notificationChannels.js'

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


test('普通聊天保留弱提示，提及和邀请参与提醒分类', () => {
  for (const type of ['project_chat','direct_chat','annotation_project_chat','discussion_chat']) assert.equal(isChatAttentionNotification({notification_type:type}),false)
  for (const type of ['project_chat_mention','annotation_project_chat_mention','direct_chat_mention','annotation_project_chat_invite','direct_chat_invite']) assert.equal(isChatAttentionNotification({notification_type:type}),true)
  assert.equal(isChatAttentionNotification({notification_type:'workflow_handover_pending'}),false)
})

test('Windows 仅通知业务未读与 @ 未读，普通消息、邀请和已读记录均不通知',()=>{
 for(const type of CHAT_NOTIFICATION_TYPES) {
  assert.equal(isDesktopAttentionNotification({notification_type:type,is_read:false}),type.endsWith('_mention'))
  assert.equal(isDesktopAttentionNotification({notification_type:type,is_read:true}),false)
 }
 assert.equal(isDesktopAttentionNotification({notification_type:'workflow_handover_pending',is_read:false}),true)
 assert.equal(isDesktopAttentionNotification({notification_type:'workflow_handover_pending',is_read:true}),false)
 assert.equal(isDesktopAttentionNotification(null),false)
})

import { runInNewContext } from 'node:vm'
import { readFileSync } from 'node:fs'
test('Windows API只收到符合数字提醒范围的通知，普通消息与已读通知不进入系统通知',()=>{
 const sent=[]
 class NativeNotification {static permission='granted';constructor(title){sent.push(title)}close(){}}
 const source=readFileSync(new URL('../src/utils/desktopNotifications.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace(/export const /g,'const ')
 const desktop=runInNewContext(`${source}; ({showDesktopNotification})`,{
  isDesktopAttentionNotification,notificationAcknowledgements:{has:()=>false,subscribe:()=>()=>{},acknowledge(){}},
  window:{Notification:NativeNotification,isSecureContext:true},
  localStorage:{getItem:key=>key==='user_id'?'alice':key==='desktop_notifications_enabled:alice'?'1':null},console,
 })
 desktop.showDesktopNotification({id:'ordinary',title:'普通消息',notification_type:'direct_chat'})
 desktop.showDesktopNotification({id:'invite',title:'群邀请',notification_type:'annotation_project_chat_invite'})
 desktop.showDesktopNotification({id:'read',title:'已读',notification_type:'direct_chat_mention',is_read:true})
 desktop.showDesktopNotification({id:'at',title:'有人@我',notification_type:'direct_chat_mention'})
 desktop.showDesktopNotification({id:'business',title:'业务待处理',notification_type:'workflow_handover_pending'})
 assert.deepEqual(sent,['有人@我','业务待处理'])
})

test('系统铃铛与会话铃铛互斥，聊天 @ 均不进入两个铃铛',()=>{
 for(const type of CHAT_NOTIFICATION_TYPES) assert.equal(isSystemNotification({notification_type:type}),false)
 for(const type of CONVERSATION_NOTIFICATION_TYPES) {
  assert.equal(isSystemNotification({notification_type:type}),false)
  assert.equal(isDesktopAttentionNotification({notification_type:type}),true)
 }
 assert.equal(isSystemNotification({notification_type:'workflow_handover_pending'}),true)
})

test('历史 annotation_project_chat 属于普通聊天，不进入系统铃铛或 Windows 通知',()=>{
 const legacy={id:'legacy-annotation',notification_type:'annotation_project_chat',related_project_type:'annotation',title:'标注群聊新消息',is_read:false}
 assert.equal(isChatNotification(legacy),true)
 assert.equal(isBusinessNotification(legacy),false)
 assert.equal(isSystemNotification(legacy),false)
 assert.equal(isChatMentionNotification(legacy),false)
 assert.equal(isDesktopAttentionNotification(legacy),false)
})

test('所有聊天家族按命名边界统一识别，新增会话类型也不能进入系统铃铛',()=>{
 for(const kind of [...CHAT_NOTIFICATION_TYPES,'interpretation_project_chat','recruitment_project_chat_mention','new_group_chat_invite',' CHAT_NEW_MESSAGE ']) {
  const item={notification_type:kind,is_read:false}
  assert.equal(isChatNotification(item),true,kind)
  assert.equal(isBusinessNotification(item),false,kind)
  assert.equal(isSystemNotification(item),false,kind)
 }
 for(const kind of ['workflow_chatty_update','chat_summary','resource_request_dispatch']) assert.equal(isChatNotification({notification_type:kind}),false,kind)
 assert.equal(isSystemNotification({notification_type:'workflow_chatty_update'}),true)
})
