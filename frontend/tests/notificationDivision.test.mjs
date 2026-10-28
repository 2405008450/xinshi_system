import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
const read=path=>readFileSync(new URL(path,import.meta.url),'utf8')
const workspace=read('../src/components/chat/ChatWorkspace.vue'),layout=read('../src/layout/index.vue'),bell=read('../src/components/NotificationBell.vue')
test('消息使用共享 @ 总数，会话铃铛仅显示自身业务通知数；互不叠加',()=>{
 const declarations=workspace.split('\n').filter(line=>/^const (mentionTotal|messageBadgeTotal|notificationBadgeTotal) = computed/.test(line)).join('\n')
 const result=runInNewContext(declarations+'; [messageBadgeTotal.value,notificationBadgeTotal.value]',{
  props:{messageNotificationTotal:7},notificationFeed:{unread:{value:3}},computed:fn=>({get value(){return fn()}}),
 })
 assert.deepEqual(Array.from(result),[7,3])
 assert.match(layout,/const \{ mentionTotal: chatMentionTotal \} = useAnnotationFollowed\(\)/)
 assert.match(read('../src/components/chat/ProjectChatDock.vue'),/:message-notification-total="mentionTotal"/)
})
test('会话铃铛点击后打开通知，不受 @ 数量影响',()=>{
 const fn=workspace.match(/function badgeClick\(key\)\{[^\n]+\}/)[0],opened=[]
 runInNewContext(fn+";badgeClick('notifications')",{selectPane:key=>opened.push(key),mentionTotal:{value:7},openUnreadMentionConversations:()=>{throw Error('不应跳转到消息')}})
 assert.deepEqual(opened,['notifications'])
})
test('系统铃铛不汇入 @，WebSocket旧业务快照不能覆盖系统专属数量',()=>{
 assert.doesNotMatch(bell,/useAnnotationFollowed|openMentionBadge|mentionTotal/)
 const fn=bell.match(/const handleSocketSnapshot = \(\) => \{[^\n]+\}/)[0]
 let refreshed=0
 runInNewContext(fn+";handleSocketSnapshot({business_unread_count:999})",{loadUnreadCount:()=>{refreshed++}})
 assert.equal(refreshed,1)
})
