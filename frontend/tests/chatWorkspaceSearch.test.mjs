import { compareMentionSessions } from '../src/utils/chatMentionSort.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { matchesSearch } from '../src/utils/searchMatching.js'
import { groupSessionList, mentionUnreadCount, firstUnreadMentionSession, compareSessionActivity } from '../src/utils/chatSessionList.js'

const source = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')
const expression = source.slice(source.indexOf('const visibleSessions ='), source.indexOf('\nfunction syncActiveConversation'))

test('列表保留置顶顺序，消息入口清除筛选并打开最新未读提及', () => {
  const sessions = [
    { key: 'read', projectType: 'annotation', pinned: true, unread: 5, mentionUnread: 0, lastMessage: { createdAt: 100 } },
    { key: 'mention-old', latestMentionAt:'2026-10-28T10:00:00+08:00', projectType: 'annotation', mentionUnread: 2, mentionMessageIds: ['old-message'], lastMessage: { createdAt: 10 } },
    { key: 'mention-new', latestMentionAt:'2026-10-28T11:00:00+08:00', projectType: 'annotation', mentionUnread: 1, mentionMessageIds: ['new-message'], lastMessage: { createdAt: 20 } },
  ]
  const pane = { value: 'settings' }, selectedFolder = { value: 'old-folder' }, tab = { value: 'starred' }
  const annotationMode = { value: 'direct' }, keyword = { value: '旧搜索' }, appliedKeyword = { value: '旧搜索' }, events = []
  const sessionList = { value: { scrollTop: 250 } }
  const handler = source.slice(source.indexOf('function openUnreadMentionConversations()'), source.indexOf('function openMobileSessions'))
  const result = runInNewContext(expression + ';' + handler + ';openUnreadMentionConversations();visibleSessions.value.map(row => row.key)', {
    props: { sessions, narrow: false, sidebarOpen: true }, computed: fn => ({ get value() { return fn() } }),
    pane, selectedFolder, tab, annotationMode, keyword, appliedKeyword, sessionList, nextTick: fn => fn(),
    applyKeyword: () => { appliedKeyword.value = keyword.value }, folderNodes: { value: [] }, annotationMentionView: { value: false },
    compareMentionSessions, mentionSort:{value:"time_desc"}, compareSessionActivity, allMentionSessions: { value: sessions }, matchesSearch, groupSessionList, firstUnreadMentionSession, sessionStamp: value => Number(value), sessionMatchesFolder: () => true,
    emit: (event, target) => events.push({ event, target }),
  })
  assert.deepEqual(Array.from(result), ['read', 'mention-new', 'mention-old'])
  assert.equal(events.length, 1)
  assert.equal(events[0].event, 'locate-mention')
  assert.equal(events[0].target.key, 'mention-new')
  assert.equal(events[0].target.messageId, 'new-message')
  assert.equal(pane.value, 'messages')
  assert.equal(selectedFolder.value, '')
  assert.equal(appliedKeyword.value, '')
  assert.equal(sessionList.value.scrollTop, 0)
})

test('顶部聊天和左侧消息入口共用打开未读会话逻辑，无未读时仅切换消息面板', () => {
  const select = source.slice(source.indexOf('function selectPane(key)'), source.indexOf('const typeLabel'))
  const header = source.match(/function showHeaderMessages\(event\) \{[^\n]+/)[0]
  let opened = 0
  const pane = { value: 'settings' }, mentionTotal = { value: 2 }
  const context = { pane, mentionTotal, projectMine: { value: false }, projectMenuVisible: { value: false }, openUnreadMentionConversations: () => { opened++ } }
  runInNewContext(select + ';' + header + ';selectPane("messages");showHeaderMessages({detail:{mentions:true}})', context)
  assert.equal(opened, 2)
  mentionTotal.value = 0
  runInNewContext(select + ';' + header + ';selectPane("messages");showHeaderMessages({detail:{mentions:false}})', context)
  assert.equal(opened, 2)
  assert.equal(pane.value, 'messages')
})
function search(folder, keyword) {
  const sessions = [
    { key: 'a', projectType: 'annotation', title: 'AABB', folder: 'annotation' },
    { key: 'b', projectType: 'discussion', title: 'AAA BBB', folder: 'resource' },
    { key: 'c', projectType: 'annotation', title: 'only AA', folder: 'annotation' },
    { key: 'd', projectType: 'direct', title: 'AABB', folder: '' },
  ]
  return runInNewContext(expression + '; visibleSessions.value.map(row => row.key)', {
    props: { sessions, searchSessions: [] }, computed: fn => ({ value: fn() }), annotationMode: { value: 'group' },
    selectedFolder: { value: folder }, folderNodes: { value: [] }, tab: { value: 'all' }, annotationMentionView: { value: false },
    appliedKeyword: { value: keyword }, compareSessionActivity, matchesSearch, groupSessionList, sessionStamp: () => 0,
    sessionMatchesFolder: (session, id) => !id || session.folder === id,
  })
}
test('关键词执行全局多关键词 AND 搜索；清空后恢复当前分组与群聊筛选', () => {
  assert.deepEqual(Array.from(search('annotation', 'AA BB')), ['a', 'b', 'd'])
  assert.deepEqual(Array.from(search('resource', 'AA BB')), ['a', 'b', 'd'])
  assert.deepEqual(Array.from(search('', 'AA BB')), ['a', 'b', 'd'])
  assert.deepEqual(Array.from(search('annotation', '')), ['a', 'c'])
})

test('通讯录发消息后切换消息单聊，清空原分组和搜索，仅显示单聊联系人', () => {
  const handler = source.match(/function contactOpened\(\) \{[\s\S]*?\n\}/)[0]
  for (const previousTab of ['all', 'unread', 'mention', 'direct']) {
    const events = [], context = {
      pane: { value: 'contacts' }, tab: { value: previousTab }, annotationMode: { value: 'group' },
      selectedFolder: { value: 'annotation' }, keyword: { value: '旧搜索' }, appliedKeyword: { value: '旧搜索' },
      applyKeyword: () => { context.appliedKeyword.value = context.keyword.value }, emit: name => events.push(name),
      props: { sessions: [
        { key: 'group', projectType: 'annotation', title: '项目群' },
        { key: 'room', projectType: 'discussion', title: '讨论' },
        { key: 'direct:1', projectType: 'direct', title: '联系人甲' },
        { key: 'direct:2', projectType: 'direct', title: '联系人乙' },
      ] },
      computed: fn => ({ value: fn() }), annotationMentionView: { value: false }, folderNodes: { value: [] },
      compareSessionActivity, matchesSearch, groupSessionList, sessionStamp: () => 0, sessionMatchesFolder: () => false,
    }
    const result = runInNewContext(handler + '; contactOpened();\n' + expression + '; visibleSessions.value.map(row => row.key)', context)
    assert.equal(context.pane.value, 'messages')
    assert.equal(context.tab.value, 'direct')
    assert.equal(context.annotationMode.value, 'direct')
    assert.equal(context.selectedFolder.value, '')
    assert.equal(context.appliedKeyword.value, '')
    assert.deepEqual(Array.from(result), ['direct:1', 'direct:2'])
    assert.deepEqual(events, ['contact-opened'])
  }
})


test('消息数字入口跳到全局 @我，清除旧分组和搜索并展开窄屏列表', () => {
  const pane={value:'contacts'}, selectedFolder={value:'status:trial_preparation'}, tab={value:'unread'}, annotationMode={value:'group'}, keyword={value:'旧关键词'}
  let applied=false, expanded=false
  const fn=source.slice(source.indexOf('function showMentionInbox()'),source.indexOf('function openUnreadMentionConversations()'))
  runInNewContext(fn+';showMentionInbox()', {pane,selectedFolder,tab,annotationMode,keyword,mentionTotal:{value:2},applyKeyword:()=>{applied=true},props:{narrow:true,sidebarOpen:false},emit:()=>{expanded=true}})
  assert.equal(pane.value,'messages'); assert.equal(selectedFolder.value,''); assert.equal(tab.value,'mention')
  assert.equal(annotationMode.value,'mention'); assert.equal(keyword.value,''); assert.ok(applied && expanded)
})


test('消息导航数字只统计未读提及，普通未读不会冒充 @我，读完提及后数字归零', () => {
  const expression=source.slice(source.indexOf('const mentionTotal = computed'),source.indexOf('function showMentionInbox'))
  const total=sessions=>runInNewContext(expression+';messageBadgeTotal.value',{props:{sessions},allMentionSessions:{value:sessions},mentionUnreadCount,computed:fn=>({get value(){return fn()}})})
  assert.equal(total([{unread:1,mentionUnread:0}]),0)
  assert.equal(total([{unread:5,mentionUnread:2},{unread:3,mentionUnread:1}]),3)
  assert.equal(total([{unread:5,mentionUnread:0},{unread:3,mentionUnread:0}]),0)
})
