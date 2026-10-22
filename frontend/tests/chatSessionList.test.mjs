import test from 'node:test'
import assert from 'node:assert/strict'
import { filterClosedSessions, groupSessionList, sessionListKey, sessionUnreadSignal, firstUnreadMentionSession } from '../src/utils/chatSessionList.js'

const row = (id, order, extra = {}) => ({ key: `annotation:${id}`, projectId: id, projectType: 'annotation', title: '同名项目', subtitle: order, ...extra })

test('自动打开未读提及时选择准确子订单和消息，不打开已读主订单', () => {
  const parent = row('parent', 'AP-261022-001', { opened: true, mentionUnread: 0 })
  const child = row('child', 'AP-261022-001.001', { mentionUnread: 2, mentionMessageIds: ['unread-message', 'another-message'] })
  const target = firstUnreadMentionSession(groupSessionList([parent, child], parent.key))
  assert.equal(target.key, child.key)
  assert.equal(target.messageId, 'unread-message')
  assert.equal(firstUnreadMentionSession([{ key: 'read', mentionUnread: 0 }]), null)
})

test('关闭主订单后目录刷新不会重新显示主订单或空白子订单，但保留其他已打开订单', () => {
  const parent = row('parent', 'AP-261007-001')
  const child = row('child', 'AP-261007-001.001')
  assert.deepEqual(filterClosedSessions([parent, child], [parent.key]), [])
  assert.deepEqual(filterClosedSessions([parent, { ...child, opened: true }], [parent.key]).map(item => item.key), [child.key])
})

test('关闭整个合并列表项后全部入口移出，重新打开子订单只恢复子订单', () => {
  const parent = row('parent', 'AP-261007-001', { opened: true })
  const child = row('child', 'AP-261007-001.001', { lastMessage: { preview: '历史消息' } })
  const catalog = [parent, child]
  const [group] = groupSessionList(catalog, parent.key)
  assert.deepEqual(group.catalogKeys, [parent.key, child.key])
  assert.deepEqual(filterClosedSessions(catalog, group.catalogKeys), [])
  assert.deepEqual(filterClosedSessions([parent, { ...child, opened: true }], [parent.key]).map(item => item.key), [child.key])
})

test('同一主订单及两级子订单只占一行，保留各自订单入口和当前打开会话', () => {
  const parent = row('parent', 'AP-261007-001', { opened: true, unread: 2 })
  const child = row('child', 'AP-261007-001.001', { opened: true, unread: 3, mentionUnread: 1 })
  const grandchild = row('grandchild', 'AP-261007-001.001.001', { lastMessage: { preview: '三级订单已有消息' } })
  const rows = groupSessionList([parent, child, grandchild, child], child.key)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].key, child.key)
  assert.equal(rows[0].opened, true)
  assert.equal(rows[0].unread, 5)
  assert.equal(rows[0].mentionUnread, 1)
  assert.deepEqual(rows[0].variants.map(item => item.projectId), ['parent', 'child', 'grandchild'])
})

test('只发起主订单聊天时，自动关注的子订单不进入切换列表', () => {
  const parent = row('parent', 'AP-261007-001', { opened: true })
  const child = row('child', 'AP-261007-001.001', { following: true })
  const [group] = groupSessionList([child, parent], parent.key)
  assert.equal(group.key, parent.key)
  assert.deepEqual(group.variants.map(item => item.key), [parent.key])
})

test('只发起子订单聊天时，不带出主订单和兄弟订单；切换其他项目后仍选中已发起的子订单', () => {
  const parent = row('parent', 'AP-261007-001', { following: true })
  const child = row('child', 'AP-261007-001.001', { opened: true })
  const sibling = row('sibling', 'AP-261007-001.002', { following: true })
  for (const activeKey of [child.key, 'annotation:other']) {
    const [group] = groupSessionList([parent, sibling, child], activeKey)
    assert.equal(group.key, child.key)
    assert.deepEqual(group.variants.map(item => item.key), [child.key])
  }
})

test('各自有历史消息的订单保留切换入口，当前订单不混入其他订单的消息预览', () => {
  const parent = row('parent', 'AP-261007-001', { lastMessage: { preview: '主订单消息' } })
  const child = row('child', 'AP-261007-001.001', { opened: true })
  const [group] = groupSessionList([parent, child], child.key)
  assert.equal(group.variants.length, 2)
  assert.equal(group.lastMessage, undefined)
})

test('尚未发起的系列只保留主订单入口，不随目录排序带出子订单', () => {
  const parent = row('parent', 'AP-261007-001')
  const child = row('child', 'AP-261007-001.001')
  const [group] = groupSessionList([child, parent])
  assert.equal(group.key, parent.key)
  assert.deepEqual(group.variants.map(item => item.key), [parent.key])
})

test('同名的不同主订单、私聊和讨论不能合并，无法识别的编号按会话身份保留', () => {
  const rows = [row('a', 'AP-261007-001'), row('b', 'AP-261007-002'), row('legacy', '历史编号'), row('legacy2', '历史编号'),
    { key: 'direct:a', projectType: 'direct', subtitle: 'AP-261007-001' },
    { key: 'discussion:a', projectType: 'discussion', subtitle: 'AP-261007-001' }]
  assert.equal(groupSessionList(rows).length, rows.length)
  assert.notEqual(sessionListKey(rows[0]), sessionListKey(rows[1]))
})

test('只有子订单在筛选结果中时仍可查看，未打开的入口保留 open 行为', () => {
  const child = row('child', 'AP-261007-001.002', { opened: false })
  const grouped = groupSessionList([child], 'annotation:outside')
  assert.equal(grouped[0].key, child.key)
  assert.equal(grouped[0].opened, false)
  assert.equal(grouped[0].variants.length, 1)
})


test('普通未读只提供圆点信号，@未读单独保留数字，混合消息两种提示可同时呈现', () => {
  assert.deepEqual(sessionUnreadSignal({unread:9,mentionUnread:0}),{mentions:0,ordinary:true})
  assert.deepEqual(sessionUnreadSignal({unread:3,mentionUnread:3}),{mentions:3,ordinary:false})
  assert.deepEqual(sessionUnreadSignal({unread:9,mentionUnread:2}),{mentions:2,ordinary:true})
  assert.deepEqual(sessionUnreadSignal({unread:0,mentionUnread:0}),{mentions:0,ordinary:false})
})
