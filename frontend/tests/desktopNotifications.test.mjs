import { isDesktopAttentionNotification } from '../src/utils/notificationChannels.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source = readFileSync(new URL('../src/utils/desktopNotifications.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '').replace(/export const /g, 'const ')
function setup({ permission = 'granted', enabled = true, throws = false, worker } = {}) {
  const instances = [], callbacks = new Set(), acknowledged = new Set()
  const values = new Map([['user_id', 'test'], ['desktop_notifications_enabled:test', enabled ? '1' : '0']])
  class Notification {
    static permission = permission
    static async requestPermission() { return permission }
    constructor(title, options) { if (throws) throw Error('failed'); this.options = options; instances.push(this) }
    close() { this.closed = true; this.onclose?.() }
  }
  const window = { Notification, isSecureContext: true, focus() {} }
  const acknowledgements = {
    has: id => acknowledged.has(id),
    acknowledge(id) { acknowledged.add(id); callbacks.forEach(fn => fn(id)) },
    subscribe(fn) { callbacks.add(fn); return () => callbacks.delete(fn) },
  }
  const api = runInNewContext(`${source}; ({ showDesktopNotification, enableDesktopNotifications, disableDesktopNotifications })`, {
    window, localStorage: { getItem: key => values.get(key), setItem: (k, v) => values.set(k, v) },
    isDesktopAttentionNotification, notificationAcknowledgements: acknowledgements, console: { error() {} },
    ...(worker ? { navigator: { serviceWorker: worker } } : {}),
  })
  return { ...api, instances, callbacks, acknowledgements, values }
}
const notification = { id: 'message-1', title: '私聊新消息', content: '点击查看' }

test('桌面发送、展示反馈与异步失败分离，重复失败仅回退一次', () => {
  const api = setup(); let shown = 0, errors = 0
  assert.equal(api.showDesktopNotification(notification, undefined, { onShow: () => shown++, onError: () => errors++ }), true)
  assert.equal(shown, 0)
  api.instances[0].onshow(); assert.equal(shown, 1)
  api.instances[0].onerror(); api.instances[0].onerror()
  assert.equal(errors, 1); assert.equal(api.callbacks.size, 0)
})

test('构造异常回退，权限拒绝和用户关闭不发送，重新启用可发送', async () => {
  const failure = setup({ throws: true }); let errors = 0
  assert.equal(failure.showDesktopNotification(notification, undefined, { onError: () => errors++ }), false)
  assert.equal(errors, 1)
  assert.equal(setup({ permission: 'denied' }).showDesktopNotification(notification), false)
  const api = setup(); api.disableDesktopNotifications()
  assert.equal(api.showDesktopNotification(notification), false)
  await api.enableDesktopNotifications()
  assert.equal(api.showDesktopNotification(notification), true)
})

test('已读确认关闭桌面通知，之后到达的异步错误不再回退', () => {
  const api = setup(); let errors = 0
  api.showDesktopNotification(notification, undefined, { onError: () => errors++ })
  api.acknowledgements.acknowledge(notification.id)
  api.instances[0].onerror()
  assert.equal(api.instances[0].closed, true); assert.equal(errors, 0)
})

function mobileWorker({ fail = false } = {}) {
  const listeners = new Set(), shown = [], closed = []
  const registration = {
    async showNotification(title, options) { if (fail) throw Error('failed'); shown.push({ title, options }) },
    async getNotifications() { return [{ close() { closed.push(true) } }] },
  }
  return { shown, closed, listeners, registration,
    getRegistration: async () => registration,
    addEventListener: (_name, callback) => listeners.add(callback),
    removeEventListener: (_name, callback) => listeners.delete(callback),
    dispatch(data) { [...listeners].forEach(callback => callback({ data })) },
  }
}
const flush = () => new Promise(resolve => setImmediate(resolve))

test('手机端通过 Service Worker 展示通知，保持同步返回值并清理点击监听', async () => {
  const worker = mobileWorker(), api = setup({ throws: true, worker })
  let shown = 0, opened = 0
  assert.equal(api.showDesktopNotification(notification, () => opened++, { onShow: () => shown++ }), true)
  await flush()
  assert.equal(worker.shown.length, 1)
  assert.equal(shown, 1)
  worker.dispatch({ type: 'NOTIFICATION_CLICKED', notificationId: notification.id })
  await flush()
  assert.equal(opened, 1)
  assert.equal(worker.listeners.size, 0)
  assert.equal(api.callbacks.size, 0)
})

test('手机端通知失败只报告一次，切换账号后不展示旧账号消息', async () => {
  const worker = mobileWorker({ fail: true }), api = setup({ throws: true, worker })
  let errors = 0
  api.showDesktopNotification(notification, undefined, { onError: () => errors++ })
  await flush()
  assert.equal(errors, 1)
  assert.equal(worker.listeners.size, 0)
  assert.equal(api.callbacks.size, 0)
  const next = mobileWorker(), switched = setup({ throws: true, worker: next })
  switched.showDesktopNotification(notification)
  switched.values.set('user_id', 'another-user')
  await flush()
  assert.equal(next.shown.length, 0)
  assert.equal(next.listeners.size, 0)
})

test('手机端已读确认关闭现有通知，用户关闭通知也清理监听', async () => {
  const worker = mobileWorker(), api = setup({ throws: true, worker })
  api.showDesktopNotification(notification)
  await flush()
  api.acknowledgements.acknowledge(notification.id)
  await flush()
  assert.equal(worker.closed.length, 1)
  assert.equal(worker.listeners.size, 0)
  const next = { ...notification, id: 'next' }
  api.showDesktopNotification(next)
  await flush()
  worker.dispatch({ type: 'NOTIFICATION_CLOSED', notificationId: next.id })
  assert.equal(worker.listeners.size, 0)
  assert.equal(api.callbacks.size, 0)
})
