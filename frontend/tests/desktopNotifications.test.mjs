import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source = readFileSync(new URL('../src/utils/desktopNotifications.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '').replace(/export const /g, 'const ')
function setup({ permission = 'granted', enabled = true, throws = false } = {}) {
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
    notificationAcknowledgements: acknowledgements, console: { error() {} },
  })
  return { ...api, instances, callbacks, acknowledgements }
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
