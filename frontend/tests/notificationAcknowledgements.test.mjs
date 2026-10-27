import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { createNotificationAcknowledgements } from '../src/utils/notificationAcknowledgements.js'
import { isChatNotification, isChatMentionNotification, isChatAttentionNotification } from '../src/utils/notificationChannels.js'

function browsers() {
  const data = new Map([['user_id', 'alice'], ['token', 'test-token']]), targets = []
  const storage = {
    getItem: key => data.get(key) ?? null,
    setItem(key, value) {
      data.set(key, value)
      for (const target of targets) target.dispatchEvent(Object.assign(new Event('storage'), { key, newValue: value, storageArea: storage }))
    },
  }
  function tab() {
    const target = new EventTarget(); targets.push(target)
    return { target, acknowledgements: createNotificationAcknowledgements({ storage: () => storage, target }) }
  }
  return { storage, tab }
}

test('确认后立即通知其他标签页，刷新后保留；同一账号的新通知仍可提醒', () => {
  const browser = browsers(), a = browser.tab(), b = browser.tab(), received = []
  const unsubscribe = b.acknowledgements.subscribe(id => received.push(id))
  a.acknowledgements.acknowledge('invite/1')
  assert.deepEqual(received, ['invite/1'])
  assert.equal(b.acknowledgements.has('invite/1'), true)
  assert.equal(browser.tab().acknowledgements.has('invite/1'), true)
  assert.equal(b.acknowledgements.has('invite/2'), false)
  unsubscribe(); a.acknowledgements.acknowledge('invite/2')
  assert.deepEqual(received, ['invite/1'])
})

test('多标签页分别确认不同通知不会覆盖；账号之间互相隔离', () => {
  const browser = browsers(), a = browser.tab(), b = browser.tab()
  a.acknowledgements.acknowledge('one'); b.acknowledgements.acknowledge('two')
  assert.equal(a.acknowledgements.has('two'), true)
  browser.storage.setItem('user_id', 'bob')
  assert.equal(a.acknowledgements.has('one'), false)
  browser.storage.setItem('user_id', 'alice')
  assert.equal(a.acknowledgements.has('one'), true)
})

test('存储不可写时保留当前标签页确认结果，且不会重复回调', () => {
  const store = createNotificationAcknowledgements({ storage: () => ({ getItem: () => null, setItem: () => { throw Error('blocked') } }), userId: () => 'alice', target: new EventTarget() })
  const received = []; store.subscribe(id => received.push(id))
  store.acknowledge('one'); store.acknowledge('one')
  assert.equal(store.has('one'), true)
  assert.deepEqual(received, ['one'])
})

const source = readFileSync(new URL('../src/composables/useChatNotifications.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export function useChatNotifications', 'function useChatNotifications')
function mountChat(browser, item, markRead = async () => {}) {
  const tab = browser.tab(), mounts = [], unmounts = [], popups = [], subscriptions = {}, opened = []
  runInNewContext(`${source}; useChatNotifications()`, {
    notificationAcknowledgements: tab.acknowledgements,
    h: () => ({}), onMounted: fn => mounts.push(fn), onBeforeUnmount: fn => unmounts.push(fn),
    useProjectChatDock: () => ({ openChat: value => opened.push(value) }),
    ElMessage: { info() {}, error() {} },
    ElNotification: options => { const popup = { options, closed: false, close() { if (!this.closed) { this.closed = true; options.onClose() } } }; popups.push(popup); return popup },
    getNotifications: async () => [{ ...item }], markNotificationRead: markRead,
    subscribe: (name, callback) => { subscriptions[name] = callback; return () => {} },
    showDesktopNotification: () => false, isChatNotification, isChatMentionNotification, isChatAttentionNotification,
    localStorage: browser.storage, window: { focus() {}, setInterval() {}, clearInterval() {} }, AbortController,
  })
  mounts.forEach(fn => fn())
  return { tab, popups, subscriptions, opened, unmount: () => unmounts.forEach(fn => fn()) }
}
const invite = { id: 'invite', notification_type: 'annotation_project_chat_invite', related_project_type: 'annotation', related_entity_id: 'project', title: '项目群聊邀请' }
const flush = () => new Promise(resolve => setImmediate(resolve))

test('点击邀请在已读请求完成前关闭两页浮窗；旧轮询、重连和新页面不会重弹', async () => {
  const browser = browsers(); let finishRead
  const a = mountChat(browser, invite, () => new Promise(resolve => { finishRead = resolve })), b = mountChat(browser, invite)
  await flush()
  const activation = a.popups[0].options.onClick()
  assert.equal(a.popups[0].closed, true); assert.equal(b.popups[0].closed, true)
  assert.equal(a.opened.length, 1); assert.equal(b.opened.length, 0)
  b.subscriptions.connected(); await flush()
  assert.equal(b.popups.length, 1)
  const c = mountChat(browser, invite); await flush(); assert.equal(c.popups.length, 0)
  finishRead(); await activation
  a.unmount(); b.unmount(); c.unmount()
})

test('页面卸载不确认邀请，用户点关闭会同步确认，新的邀请继续弹出', async () => {
  const browser = browsers(), a = mountChat(browser, invite), b = mountChat(browser, invite)
  await flush(); a.unmount()
  assert.equal(b.tab.acknowledgements.has(invite.id), false)
  assert.equal(b.popups[0].closed, false)
  b.popups[0].close()
  assert.equal(b.tab.acknowledgements.has(invite.id), true)
  b.subscriptions.notification({ notification: { ...invite, id: 'new-invite' } })
  assert.equal(b.popups.length, 2)
  b.unmount()
})

test('关闭 @ 浮窗后切换页面、恢复前台和重连均不重弹，也不将消息标为已读', async () => {
  const browser = browsers(), mention = { ...invite, id: 'mention', notification_type: 'annotation_project_chat_mention' }
  let reads = 0
  const a = mountChat(browser, mention, async () => { reads++ })
  await flush()
  a.popups[0].close()
  assert.equal(reads, 0)
  assert.equal(mention.is_read, undefined)
  a.unmount()
  const b = mountChat(browser, mention, async () => { reads++ })
  await flush()
  b.subscriptions.foreground(); await flush()
  b.subscriptions.connected(); await flush()
  assert.equal(b.popups.length, 0)
  assert.equal(reads, 0)
  b.subscriptions.notification({ notification: { ...mention, id: 'new-mention' } })
  assert.equal(b.popups.length, 1)
  b.unmount()
})
