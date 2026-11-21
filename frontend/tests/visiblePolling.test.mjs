import test from 'node:test'
import assert from 'node:assert/strict'
import { createVisiblePolling } from '../src/utils/visiblePolling.js'

function setup(options = {}) {
  let visible = true, clock = 1000, id = 0, calls = 0
  const timers = new Map(), listeners = new Set()
  const target = {
    addEventListener: (_, fn) => listeners.add(fn),
    removeEventListener: (_, fn) => listeners.delete(fn),
  }
  const polling = createVisiblePolling({
    task: async () => { calls++ }, visibleMs: 30000, hiddenMs: null, target,
    isVisible: () => visible, now: () => clock,
    setTimer: (fn, ms) => { timers.set(++id, { fn, ms }); return id },
    clearTimer: key => timers.delete(key),
    ...options,
  })
  return {
    polling, timers, listeners, calls: () => calls,
    advance: ms => { clock += ms },
    setVisible: value => { visible = value; listeners.forEach(fn => fn()) },
    fire: async () => { const [key, item] = [...timers.entries()][0]; timers.delete(key); await item.fn() },
  }
}

test('可见时按间隔轮询，停止后清理定时器与监听', async () => {
  const ctx = setup()
  ctx.polling.start()
  assert.equal(ctx.timers.size, 1); assert.equal([...ctx.timers.values()][0].ms, 30000)
  await ctx.fire(); assert.equal(ctx.calls(), 1); assert.equal(ctx.timers.size, 1)
  ctx.polling.stop(); assert.equal(ctx.timers.size, 0); assert.equal(ctx.listeners.size, 0)
})

test('隐藏且 hiddenMs 为空时暂停，恢复可见后补查并继续轮询', async () => {
  const ctx = setup()
  ctx.polling.start()
  ctx.setVisible(false); assert.equal(ctx.timers.size, 0); assert.equal(ctx.calls(), 0)
  ctx.advance(60000); ctx.setVisible(true)
  await Promise.resolve(); assert.equal(ctx.calls(), 1); assert.equal(ctx.timers.size, 1)
})

test('隐藏时可使用更慢的兜底间隔', () => {
  const ctx = setup({ hiddenMs: 120000 })
  ctx.polling.start(); ctx.setVisible(false)
  assert.equal([...ctx.timers.values()][0].ms, 120000)
})

test('短时间内重复触发合并为一次，强制触发不受限制', async () => {
  const ctx = setup()
  await ctx.polling.trigger(false); await ctx.polling.trigger(false)
  assert.equal(ctx.calls(), 1)
  await ctx.polling.trigger(true); assert.equal(ctx.calls(), 2)
  ctx.advance(20000); await ctx.polling.trigger(false); assert.equal(ctx.calls(), 3)
})

test('任务仍在执行时不会并发启动第二次', async () => {
  let release, calls = 0
  const ctx = setup({ task: () => { calls++; return new Promise(done => { release = done }) } })
  const first = ctx.polling.trigger(true); void ctx.polling.trigger(true)
  assert.equal(calls, 1); release(); await first
})

test('任务抛错不会中断后续轮询', async () => {
  const ctx = setup({ task: async () => { throw new Error('offline') } })
  ctx.polling.start(); await ctx.fire(); assert.equal(ctx.timers.size, 1)
})
