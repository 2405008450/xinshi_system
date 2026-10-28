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


test('普通聊天不弹窗或桌面提醒，@提及和邀请保留主动提醒', () => {
  for (const type of ['project_chat','direct_chat']) assert.equal(isChatAttentionNotification({notification_type:type}),false)
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
