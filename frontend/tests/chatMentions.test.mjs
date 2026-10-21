import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source = readFileSync(new URL('../src/composables/useChatMentions.js', import.meta.url), 'utf8')

function harness() {
  const mounted = [], unmounted = [], watches = [], requests = [], events = new Map(), timers = new Map()
  let serial = 0
  const context = {
    ref: value => ({ value }),
    watch: (target, callback) => watches.push({ target, callback }),
    onMounted: callback => mounted.push(callback), onBeforeUnmount: callback => unmounted.push(callback),
    subscribe: (name, callback) => { events.set(name, callback); return () => events.delete(name) },
    localStorage: { getItem: () => 'test-user' }, AbortController,
    setTimeout: callback => { const id = ++serial; timers.set(id, callback); return id },
    clearTimeout: id => timers.delete(id), setInterval: () => ++serial, clearInterval: () => {},
    chatRequest: (path, options) => new Promise((resolve, reject) => requests.push({ path, ...options, resolve, reject })),
  }
  runInNewContext(source.replace(/^import .+\r?\n/gm, '').replace('export function', 'function'), context)
  const keyword = { value: '' }, active = { value: true }, filters = { value: {} }
  const state = context.useChatMentions(keyword, active, filters)
  const change = async (target, value) => {
    target.value = value
    watches.find(item => item.target === target).callback(value)
    await settle()
  }
  return { state, requests, events, keyword, active, filters, change, mount: () => mounted.forEach(fn => fn()),
    stop: () => unmounted.forEach(fn => fn()), fire: () => { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(fn => fn()) } }
}
const settle = async () => { for (let i = 0; i < 5; i++) await Promise.resolve() }
const data = (items, more = false, total = items.length) => ({ items, total, hasMore: more, nextBefore: more ? items.at(-1).sequenceNo : null })
const message = seq => ({ messageId: `m${seq}`, sequenceNo: seq })

test('状态与关键词共同分页，切换状态取消旧请求，返回全局提及移除状态限制', async () => {
  const h = harness(); h.keyword.value = '确认'
  h.filters.value = { projectType: 'annotation', projectStatus: 'trial_in_progress' }; h.mount()
  h.requests[0].resolve(data([message(80)], true, 2)); await settle()
  const more = h.state.loadMore()
  assert.equal(h.requests[1].params.project_type, 'annotation')
  assert.equal(h.requests[1].params.project_status, 'trial_in_progress')
  assert.equal(h.requests[1].params.keyword, '确认')
  assert.equal(h.requests[1].params.before, 80)
  await h.change(h.filters, { projectType: 'annotation', projectStatus: 'client_feedback' })
  assert.equal(h.requests[1].signal.aborted, true)
  assert.equal(h.requests[2].params.before, null)
  assert.equal(h.state.total.value, 0)
  h.requests[2].resolve(data([message(50)])); await settle()
  h.requests[1].resolve(data([message(79)])); await more
  assert.deepEqual(Array.from(h.state.items.value, row => row.messageId), ['m50'])
  await h.change(h.filters, {})
  assert.equal(h.requests[3].params.project_type, undefined)
  assert.equal(h.requests[3].params.project_status, undefined)
  h.requests[3].resolve(data([message(90), message(50)])); await settle()
  assert.equal(h.state.total.value, 2)
  h.stop()
})

test('历史提及搜索取消前一请求，迟到响应不能覆盖最新结果', async () => {
  const h = harness(); h.mount()
  await h.change(h.keyword, '旧消息')
  assert.equal(h.requests[0].signal.aborted, true)
  await h.change(h.keyword, '新消息')
  assert.equal(h.requests[1].signal.aborted, true)
  h.requests[2].resolve(data([message(3)])); await settle()
  h.requests[1].resolve(data([message(1)])); h.requests[0].resolve(data([message(0)])); await settle()
  assert.deepEqual(Array.from(h.state.items.value, row => row.messageId), ['m3'])
  assert.equal(h.state.total.value, 1)
  assert.equal(h.requests[2].params.keyword, '新消息')
  await h.change(h.keyword, '')
  assert.equal(h.requests.length, 4)
  assert.equal(h.requests[3].params.before, null)
  h.stop()
})

test('加载更多沿用同一筛选和游标，重复消息去重，离开面板取消请求', async () => {
  const h = harness(); h.keyword.value = '确认'; h.mount()
  h.requests[0].resolve(data([message(8), message(7)], true, 4)); await settle()
  const pending = h.state.loadMore()
  assert.equal(h.requests[1].params.before, 7)
  assert.equal(h.requests[1].params.keyword, '确认')
  h.requests[1].resolve(data([message(7), message(6)], false, 4)); await pending
  assert.deepEqual(Array.from(h.state.items.value, row => row.messageId), ['m8', 'm7', 'm6'])
  assert.equal(h.state.hasMore.value, false)
  const reload = h.state.reload()
  await h.change(h.active, false)
  assert.equal(h.requests[2].signal.aborted, true)
  h.requests[2].resolve(data([message(100)])); await reload
  assert.equal(h.state.items.value.length, 0)
  assert.equal(h.state.loading.value, false)
  h.stop(); assert.equal(h.events.size, 0)
})

test('实时刷新保留已展开的历史范围，并移除撤回消息', async () => {
  const h = harness(); h.mount()
  const first = Array.from({ length: 50 }, (_, i) => message(100 - i))
  h.requests[0].resolve(data(first, true, 60)); await settle()
  const more = h.state.loadMore()
  h.requests[1].resolve(data(Array.from({ length: 10 }, (_, i) => message(50 - i)), false, 60)); await more
  h.events.get('chat_message')(); h.fire()
  // 撤回第 100 条后，新消息 101 补入第一页，旧的第二页仍需刷新。
  h.requests[2].resolve(data([message(101), ...first.slice(1)], true, 60)); await settle()
  assert.equal(h.requests[3].params.before, 51)
  h.requests[3].resolve(data(Array.from({ length: 10 }, (_, i) => message(50 - i)), false, 60)); await settle()
  assert.equal(h.state.items.value.length, 60)
  assert.equal(h.state.items.value[0].messageId, 'm101')
  assert.equal(h.state.items.value.some(row => row.messageId === 'm100'), false)
  h.stop()
})

test('失败不吞掉错误，重试可恢复历史提及列表', async () => {
  const h = harness(); h.mount()
  h.requests[0].reject({ detail: '暂时无法加载' }); await settle()
  assert.equal(h.state.error.value, '暂时无法加载')
  assert.equal(h.state.loading.value, false)
  const retry = h.state.reload()
  h.requests[1].resolve(data([message(1)])); await retry
  assert.equal(h.state.error.value, '')
  assert.equal(h.state.items.value.length, 1)
  h.stop()
})
