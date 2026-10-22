import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { chatEntryContext } from '../src/utils/chatEntryContext.js'

test('板块入口映射对应分组，工作台和资源子页面不误判为项目板块', () => {
  for (const type of ['annotation', 'translation', 'interpretation', 'recruitment']) {
    assert.equal(chatEntryContext({ path: `/${type}-details` }), type)
  }
  assert.equal(chatEntryContext({ path: '/translation-sub-orders/123' }), 'translation')
  assert.equal(chatEntryContext({ path: '/resource-management/recruitment-talents', meta: { chatContext: 'resource' } }), 'resource')
  assert.equal(chatEntryContext({ path: '/workbench' }), '')
})

const source = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')
const handler = source.slice(source.indexOf("let pendingContextFolder = ''"), source.indexOf("onMounted(() => window.addEventListener('chat-topic-show-annotation'"))
function setup(rows = []) {
  let retry
  const events = [], context = {
    pane: { value: 'topics' }, annotationMode: { value: 'mention' }, tab: { value: 'starred' },
    keyword: { value: 'old' }, selectedFolder: { value: 'resource' }, sessionList: { value: { scrollTop: 99 } },
    folderTreeRef:{value:{reveal:id=>{context.revealedFolder=id}}},
    folderNodes: { value: [{ id: 'annotation', ruleKey: 'annotation' }, { id: 'resource', ruleKey: 'resource' }] },
    visibleSessions: { value: rows }, props: { sessions: rows }, applyKeyword() { context.keyword.value = '' },
    watch: (_, callback) => { retry = callback }, nextTick: fn => fn(), emit: (...args) => events.push(args),
    openUnreadMentionConversations: () => events.push(['mentions']),
  }
  runInNewContext(handler, context)
  return { context, events, retry: () => retry() }
}

test('从板块进入清除旧筛选并打开该组首条，已有会话复用', () => {
  for (const opened of [true, false]) {
    const first = { key: 'first', opened }, { context, events } = setup([first, { key: 'second' }])
    context.showHeaderMessages({ detail: { context: 'annotation', mentions: true } })
    assert.equal(context.pane.value, 'messages')
    assert.equal(context.selectedFolder.value, 'annotation')
    assert.equal(context.revealedFolder, 'annotation')
    assert.equal(context.annotationMode.value, 'group')
    assert.equal(context.keyword.value, '')
    assert.equal(events[1][0], opened ? 'select' : 'open')
    assert.equal(events[1][1], first)
    assert.equal(context.sessionList.value.scrollTop, 0)
  }
})

test('空分组清除旧会话，异步加载首条后仅打开一次，用户切组后不抢焦点', () => {
  const { context, events, retry } = setup()
  context.showHeaderMessages({ detail: { context: 'annotation' } })
  assert.deepEqual(events.map(row => row[0]), ['context-empty'])
  context.visibleSessions.value = [{ key: 'loaded' }]
  retry(); retry()
  assert.deepEqual(events.map(row => row[0]), ['context-empty', 'open'])
  context.showHeaderMessages({ detail: { context: 'resource' } })
  context.visibleSessions.value = []
  context.showHeaderMessages({ detail: { context: 'annotation' } })
  context.selectedFolder.value = 'resource'
  context.visibleSessions.value = [{ key: 'other' }]
  const before = events.length
  retry()
  assert.equal(events.length, before)
})
