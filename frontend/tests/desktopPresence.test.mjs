import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { ref, watch, nextTick } from 'vue'

const source = readFileSync(new URL('../src/composables/useDesktopPresence.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export function ', 'function ')
function harness(ids) {
  const requests = [], unmounts = [], subscriptions = new Map(), stops = []
  const userIds = ref(ids), active = ref(true)
  const usePresence = runInNewContext(source + ';useDesktopPresence', {
    ref, watch: (...args) => { const stop = watch(...args); stops.push(stop); return stop },
    onBeforeUnmount: fn => unmounts.push(fn), AbortController,
    localStorage: { getItem: () => 'qa' }, setInterval: () => 1, clearInterval() {},
    subscribe: (type, fn) => { subscriptions.set(type, fn); return () => subscriptions.delete(type) },
    chatRequest: (path, options) => new Promise((resolve, reject) => requests.push({ path, ...options, resolve, reject })),
  })
  const store = usePresence(userIds, active)
  return { store, userIds, active, requests, subscriptions, unmount() { unmounts.forEach(fn => fn()); stops.forEach(fn => fn()) } }
}
const flush = async () => { await nextTick(); for (let i = 0; i < 6; i++) await Promise.resolve() }

test('超过200位候选批量获取电脑与排班状态，排除所有人并去重', async () => {
  const h = harness(['__all__', ...Array.from({ length: 201 }, (_, index) => `user-${index}`), 'user-0'])
  assert.equal(h.requests[0].data.userIds.length, 200)
  h.requests[0].resolve({ items: [{ userId: 'user-0', desktopOnline: true, workState: 'off_hours' }] })
  await flush()
  assert.equal(h.requests[1].data.userIds.length, 1)
  h.requests[1].resolve({ items: [{ userId: 'user-200', desktopOnline: false, workState: 'working' }] })
  await flush()
  assert.equal(h.store.statuses.value['user-0'], true)
  assert.equal(h.store.workStatuses.value['user-0'].workState, 'off_hours')
  assert.equal(h.store.statuses.value['user-200'], false)
  h.unmount()
})

test('重连和前台恢复立即刷新，迟到响应不会覆盖状态，关闭和卸载取消请求', async () => {
  const h = harness(['one'])
  h.subscriptions.get('connected')()
  assert.equal(h.requests[0].signal.aborted, true)
  h.requests[1].resolve({ items: [{ userId: 'one', desktopOnline: true, workState: 'working' }] }); await flush()
  h.requests[0].resolve({ items: [{ userId: 'one', desktopOnline: false }] }); await flush()
  assert.equal(h.store.statuses.value.one, true)
  h.subscriptions.get('foreground')()
  h.active.value = false; await flush()
  assert.equal(h.requests[2].signal.aborted, true)
  assert.equal(Object.keys(h.store.statuses.value).length, 0)
  assert.equal(Object.keys(h.store.workStatuses.value).length, 0)
  h.unmount()
  assert.equal(h.subscriptions.size, 0)
})

test('状态查询失败显示未知，避免残留在线或加班提示', async () => {
  const h = harness(['one'])
  h.requests[0].resolve({ items: [{ userId: 'one', desktopOnline: true, workState: 'off_hours' }] }); await flush()
  h.subscriptions.get('foreground')()
  h.requests[1].reject(Error('offline')); await flush()
  assert.equal(Object.keys(h.store.statuses.value).length, 0)
  assert.equal(Object.keys(h.store.workStatuses.value).length, 0)
  h.unmount()
})
