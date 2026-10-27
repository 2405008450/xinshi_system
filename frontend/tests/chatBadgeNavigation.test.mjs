import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {firstUnreadMentionSession,groupSessionList} from '../src/utils/chatSessionList.js'
import {compareMentionSessions} from '../src/utils/chatMentionSort.js'
const workspace=readFileSync(new URL('../src/components/chat/ChatWorkspace.vue',import.meta.url),'utf8')
const functions=[workspace.match(/function openFolderUnread\(id\)\{[\s\S]*?\n\}/)[0],workspace.match(/function openUnreadMentionConversations\(\) \{[\s\S]*?\n\}/)[0],workspace.match(/^function badgeClick.*$/m)[0]].join('\n')
function harness(sessions,hidden=[]){
  const events=[],ref=value=>({value}),context={pane:ref('notifications'),selectedFolder:ref(''),tab:ref('all'),annotationMode:ref('group'),keyword:ref('old'),props:{sessions,searchSessions:hidden,narrow:true,sidebarOpen:false},mentionTotal:ref(sessions.reduce((n,s)=>n+(s.mentionUnread||0),0)),applyKeyword(){},nextTick:fn=>fn(),sessionList:ref(null),emit:(...args)=>events.push(args),selectPane:key=>events.push(['pane',key]),firstUnreadMentionSession,compareMentionSessions}
  context.allMentionSessions={get value(){return [...sessions,...hidden]}}
  context.visibleSessions={get value(){return groupSessionList(context.allMentionSessions.value.filter(s=>!context.selectedFolder.value||s.folder===context.selectedFolder.value),'')}}
  return {...runInNewContext(`${functions};({openFolderUnread,badgeClick})`,context),context,events}
}
test('分组红色数字定位子订单中的具体未读消息，排除其他分组',()=>{
  const parent={key:'annotation:parent',projectType:'annotation',subtitle:'AP-261027-001',folder:'annotation',mentionUnread:0}
  const child={key:'annotation:child',projectId:'child',projectType:'annotation',subtitle:'AP-261027-001.001',folder:'annotation',mentionUnread:2,mentionMessageIds:['exact-message']}
  const h=harness([parent,child,{key:'discussion:other',projectType:'discussion',folder:'resource',mentionUnread:1,mentionMessageIds:['wrong']}])
  h.openFolderUnread('annotation')
  const target=h.events.find(e=>e[0]==='locate-mention')[1]
  assert.equal(target.projectId,'child');assert.equal(target.messageId,'exact-message')
  assert.equal(h.context.selectedFolder.value,'annotation')
})
test('铃铛数字使用消息数字的定位流程，也支持单聊提及',()=>{
  const h=harness([{key:'direct:d',projectId:'d',projectType:'direct',mentionUnread:1,mentionMessageIds:['direct-message'],latestMentionAt:'2026-10-27T12:00:00+08:00'}])
  h.badgeClick('notifications')
  assert.equal(h.events.find(e=>e[0]==='locate-mention')[1].messageId,'direct-message')
  assert.equal(h.context.annotationMode.value,'direct')
  const empty=harness([]);empty.badgeClick('notifications');assert.equal(empty.events[0][0],'pane')
})
test('顶部铃铛仅点击数字时跳转 @我，点击图标保留业务通知入口',async()=>{
  const source=readFileSync(new URL('../src/components/NotificationBell.vue',import.meta.url),'utf8').match(/async function openMentionBadge\(event\)\{[\s\S]*?\n\}/)[0]
  const events=[]
  const open=runInNewContext(`${source};openMentionBadge`,{mentionTotal:{value:1},popoverVisible:{value:true},useProjectChatDock:()=>({openFullscreen:()=>events.push('open')}),nextTick:async()=>{},window:{dispatchEvent:e=>events.push(e.detail)},CustomEvent:class{constructor(type,options){this.detail=options.detail}}})
  await open({target:{closest:()=>false}});assert.equal(events.length,0)
  await open({target:{closest:()=>true},preventDefault(){},stopPropagation(){}})
  assert.equal(events[0],'open');assert.equal(events[1].mentions,true)
})


test('已关闭但仍有未读提及的会话也能通过数字准确恢复和定位',()=>{
  const h=harness([],[{key:'annotation:closed',projectId:'closed',projectType:'annotation',folder:'annotation',mentionUnread:1,mentionMessageIds:['closed-message']}])
  h.context.mentionTotal.value=1
  h.openFolderUnread('annotation')
  assert.equal(h.events.find(e=>e[0]==='locate-mention')[1].messageId,'closed-message')
  h.events.length=0;h.badgeClick('notifications')
  assert.equal(h.events.find(e=>e[0]==='locate-mention')[1].projectId,'closed')
})
