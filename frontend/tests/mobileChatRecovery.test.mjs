import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { computed, ref } from 'vue'
import { isChatNotification, isChatMentionNotification, isChatAttentionNotification } from '../src/utils/notificationChannels.js'

function events(extra = {}) {
  const handlers = new Map()
  return Object.assign({
    addEventListener(type, fn) { if (!handlers.has(type)) handlers.set(type, new Set()); handlers.get(type).add(fn) },
    removeEventListener(type, fn) { handlers.get(type)?.delete(fn) },
    fire(type, extra = {}) { for (const fn of handlers.get(type) || []) fn({ type, ...extra }) },
  }, extra)
}
function harness() {
  let now = 1000, nextTimer = 0
  const intervals = new Map(), timeouts = new Map(), sockets = [], storage = new Map([['token', 'test-only']])
  const window = events({
    setTimeout(fn) { const id = ++nextTimer; timeouts.set(id, fn); return id },
    clearTimeout(id) { timeouts.delete(id) },
    setInterval(fn) { const id = ++nextTimer; intervals.set(id, fn); return id },
    clearInterval(id) { intervals.delete(id) },
  })
  const document = events({ visibilityState: 'visible' })
  class Socket {
    static CONNECTING = 0; static OPEN = 1; static CLOSED = 3
    readyState = 0; sent = []
    open() { this.readyState = 1; this.onopen?.() }
    message(payload) { this.onmessage?.({ data: JSON.stringify(payload) }) }
    send(value) { this.sent.push(value) }
    close() { this.readyState = 3; this.onclose?.() }
  }
  const source = readFileSync(new URL('../src/utils/realtimeSocket.js', import.meta.url), 'utf8')
  const api = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replaceAll('export const ', 'const ') + '\n;({ensureConnected,closeSocket,subscribe,watchAnnotationChat})', {
    window, document, localStorage: { getItem: key => storage.get(key) }, WebSocket: Socket,
    Date: { now: () => now }, console,
    createNotificationSocket() { const socket = new Socket(); sockets.push(socket); return socket },
  })
  return { ...api, sockets, document, window, storage, advance(ms) { now += ms },
    heartbeat() { for (const fn of [...intervals.values()]) fn() } }
}

test('手机恢复后重建假 OPEN 连接，恢复项目订阅并忽略旧连接事件', () => {
  const h = harness(), foreground = [], messages = []
  h.subscribe('foreground', item => foreground.push(item))
  h.subscribe('notification', item => messages.push(item))
  h.watchAnnotationChat('project-a'); const first = h.sockets[0]; first.open()
  h.document.visibilityState = 'hidden'; h.document.fire('visibilitychange')
  assert.equal(foreground.length, 0)
  h.advance(60000); h.document.visibilityState = 'visible'; h.document.fire('visibilitychange')
  assert.equal(h.sockets.length, 2)
  assert.equal(first.readyState, 3)
  assert.equal(foreground.length, 1)
  h.sockets[1].open()
  assert.ok(h.sockets[1].sent.some(value => JSON.parse(value).projectId === 'project-a'))
  first.message({ type: 'notification', id: 'stale' })
  assert.equal(messages.length, 0)
  h.sockets[1].message({ type: 'notification', id: 'current' })
  assert.equal(messages.length, 1)
})

test('短暂切换仍补查未读，连续前台事件合并，网络恢复强制重连', () => {
  const h = harness(); let resumes = 0
  h.subscribe('foreground', () => resumes++)
  h.ensureConnected().open()
  h.advance(2000); h.window.fire('focus'); h.window.fire('pageshow')
  assert.equal(resumes, 1)
  assert.equal(h.sockets.length, 1)
  h.advance(1000); h.window.fire('online')
  assert.equal(h.sockets.length, 2)
  assert.equal(resumes, 2)
})

test('心跳超时重连，pong 延续存活，挂起的 CONNECTING 连接恢复后重建', () => {
  const h = harness(); h.ensureConnected().open()
  h.advance(50000); h.sockets[0].message({ type: 'pong' }); h.heartbeat()
  assert.equal(h.sockets.length, 1)
  h.advance(80000); h.heartbeat()
  assert.equal(h.sockets.length, 2)
  h.advance(16000); h.window.fire('focus')
  assert.equal(h.sockets.length, 3)
})

test('退出登录后前台事件不复活连接，再次登录可恢复监听', () => {
  const h = harness(); h.ensureConnected().open(); h.closeSocket()
  h.advance(100000); h.window.fire('online'); h.document.fire('resume')
  assert.equal(h.sockets.length, 1)
  h.storage.delete('token'); h.ensureConnected()
  assert.equal(h.sockets.length, 1)
  h.storage.set('token', 'second-login'); h.ensureConnected().open()
  h.advance(1000); h.window.fire('online')
  assert.equal(h.sockets.length, 3)
})

test('短暂后台返回也立即换连接，网络恢复不被 focus 合并吞掉', () => {
  const h = harness(); h.ensureConnected().open()
  h.window.fire('focus')
  h.window.fire('online')
  assert.equal(h.sockets.length, 2)
  h.sockets[1].open()
  h.document.visibilityState = 'hidden'; h.document.fire('visibilitychange')
  h.advance(100); h.document.visibilityState = 'visible'; h.document.fire('visibilitychange')
  assert.equal(h.sockets.length, 3)
})

const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve() }
function lifecycle() {
  const mounts = [], unmounts = [], subscribers = new Map(), requests = []
  return {
    mounts, unmounts, subscribers, requests,
    onMounted: fn => mounts.push(fn), onBeforeUnmount: fn => unmounts.push(fn),
    localStorage: { getItem: key => ({ token: 'test-only', user_id: 'actor' })[key] },
    window: { setInterval: () => 1, clearInterval() {} }, AbortController, console,
    subscribe(type, fn) { subscribers.set(type, fn); return () => subscribers.delete(type) },
    request(options) { return new Promise(resolve => requests.push({ ...options, resolve })) },
  }
}

test('前台恢复立即补查会话，旧挂起请求迟到也不能覆盖新未读数', async () => {
  const h = lifecycle()
  const source = readFileSync(new URL('../src/composables/useAnnotationFollowed.js', import.meta.url), 'utf8')
  const useStore = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replace('export function ', 'function ') + '\n;useAnnotationFollowed', {
    ...h, ref, computed, chatRequest: (_path, options) => h.request(options),
    ensureConnected() {}, applySessionCategories() {},
    useChatTopics: () => ({ refresh: async () => {} }), useProjectChatDock: () => ({ state: { windows: [] } }),
    refreshOpenAnnotationStatuses: async () => {},
  })
  const store = useStore(); h.mounts.forEach(fn => fn())
  assert.equal(h.requests.length, 1)
  h.subscribers.get('foreground')()
  assert.equal(h.requests.length, 2)
  assert.equal(h.requests[0].signal.aborted, true)
  h.requests[1].resolve({ items: [{ key: 'new', kind: 'annotation', mentionUnread: 4 }], mentionTotal: 4 })
  await flush()
  assert.equal(store.mentionTotal.value, 4)
  h.requests[0].resolve({ items: [], mentionTotal: 0 }); await flush()
  assert.equal(store.mentionTotal.value, 4)
  store.refresh(); assert.equal(h.requests.length, 3)
  h.unmounts.forEach(fn => fn())
  h.requests[2].resolve({ items: [], mentionTotal: 99 }); await flush()
  assert.equal(store.mentionTotal.value, 0)
})

test('恢复补查未读提醒，忽略旧响应并避免实时事件和补查重复弹窗', async () => {
  const h = lifecycle(), displayed = []
  const source = readFileSync(new URL('../src/composables/useChatNotifications.js', import.meta.url), 'utf8')
  const useNotifications = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replace('export function ', 'function ') + '\n;useChatNotifications', {
    ...h, h: (...args) => args, ElMessage: { info() {}, error() {} },
    ElNotification: options => { displayed.push(options); return { close() {} } },
    getNotifications: (params, options) => h.request({ params, ...options }),
    useProjectChatDock: () => ({ openChat() {} }), showDesktopNotification: () => false,
    isChatNotification, isChatMentionNotification, isChatAttentionNotification,
    notificationAcknowledgements:{has:()=>false,acknowledge:()=>{},subscribe:()=>()=>{}},
  })
  useNotifications(); h.mounts.forEach(fn => fn())
  h.subscribers.get('foreground')()
  assert.equal(h.requests[0].signal.aborted, true)
  assert.equal(h.requests[1].params.unread_only, true)
  const item = { id: 'mention-1', notification_type: 'annotation_project_chat_mention', is_read: false }
  h.requests[1].resolve([item]); await flush()
  assert.equal(displayed.length, 1)
  h.requests[0].resolve([{ ...item, id: 'obsolete' }]); await flush()
  assert.equal(displayed.length, 1)
  h.subscribers.get('notification')({ notification: item })
  assert.equal(displayed.length, 1)
  h.unmounts.forEach(fn => fn())
})
