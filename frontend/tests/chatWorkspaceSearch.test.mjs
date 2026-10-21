import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { matchesSearch } from '../src/utils/searchMatching.js'

const source = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')
const expression = source.slice(source.indexOf('const visibleSessions ='), source.indexOf('\nfunction showAnnotation'))
function search(folder, keyword) {
  const sessions = [
    { key: 'a', projectType: 'annotation', title: 'AABB', folder: 'annotation' },
    { key: 'b', projectType: 'discussion', title: 'AAA BBB', folder: 'resource' },
    { key: 'c', projectType: 'annotation', title: 'only AA', folder: 'annotation' },
    { key: 'd', projectType: 'direct', title: 'AABB', folder: '' },
  ]
  return runInNewContext(expression + '; visibleSessions.value.map(row => row.key)', {
    props: { sessions }, computed: fn => ({ value: fn() }), annotationMode: { value: 'group' },
    selectedFolder: { value: folder }, folderNodes: { value: [] }, tab: { value: 'all' }, annotationMentionView: { value: false },
    appliedKeyword: { value: keyword }, matchesSearch, sessionStamp: () => 0,
    sessionMatchesFolder: (session, id) => !id || session.folder === id,
  })
}
test('搜索先限定分组，再执行多关键词 AND；全部分组可跨组，群聊不混入私聊', () => {
  assert.deepEqual(Array.from(search('annotation', 'AA BB')), ['a'])
  assert.deepEqual(Array.from(search('resource', 'AA BB')), ['b'])
  assert.deepEqual(Array.from(search('', 'AA BB')), ['a', 'b'])
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
      matchesSearch, sessionStamp: () => 0, sessionMatchesFolder: () => false,
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
