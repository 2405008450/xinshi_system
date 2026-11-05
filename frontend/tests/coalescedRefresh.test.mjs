import assert from 'node:assert/strict'
import test from 'node:test'
import { createCoalescedRefresh } from '../src/utils/coalescedRefresh.js'

function clock() {
  let time = 0
  let id = 0
  const tasks = new Map()
  return {
    now: () => time,
    setTimer: (run, delay) => { tasks.set(++id, { run, at: time + delay }); return id },
    clearTimer: key => tasks.delete(key),
    async advance(ms) {
      time += ms
      for (const [key, task] of [...tasks]) {
        if (task.at <= time) { tasks.delete(key); void task.run() }
      }
      await Promise.resolve()
      await Promise.resolve()
    },
    size: () => tasks.size,
  }
}

test('突发事件只刷新一次，下一次遵守最小间隔', async () => {
  const timer = clock()
  let count = 0
  const queue = createCoalescedRefresh(async () => { count++ }, timer)
  const requests = Array.from({ length: 30 }, () => queue.schedule())
  assert.equal(timer.size(), 1)
  await timer.advance(399)
  assert.equal(count, 0)
  await timer.advance(1)
  await Promise.all(requests)
  assert.equal(count, 1)
  queue.schedule({ immediate: true })
  await timer.advance(2999)
  assert.equal(count, 1)
  await timer.advance(1)
  assert.equal(count, 2)
})

test('慢请求期间不取消或并发，后续事件合并且 await 等到刷新完成', async () => {
  const timer = clock()
  let release
  let count = 0
  const queue = createCoalescedRefresh(() => {
    count++
    return new Promise(resolve => { release = resolve })
  }, timer)
  queue.schedule({ immediate: true })
  await timer.advance(0)
  let completed = false
  const followup = queue.schedule().then(() => { completed = true })
  for (let i = 0; i < 20; i++) queue.schedule()
  await timer.advance(5000)
  assert.equal(count, 1)
  assert.equal(completed, false)
  release()
  await timer.advance(0)
  await timer.advance(400)
  assert.equal(count, 2)
  assert.equal(completed, false)
  release()
  await followup
  assert.equal(completed, true)
})

test('隐藏时暂停刷新，恢复可立即更新，卸载清理队列', async () => {
  const timer = clock()
  let visible = false
  let count = 0
  const queue = createCoalescedRefresh(async () => { count++ }, { ...timer, visible: () => visible })
  await queue.schedule()
  assert.equal(timer.size(), 0)
  visible = true
  await timer.advance(0)
  const pending = queue.schedule({ immediate: true })
  await timer.advance(0)
  await pending
  assert.equal(count, 1)
  const cancelled = queue.schedule()
  queue.stop()
  await cancelled
  await timer.advance(10000)
  assert.equal(count, 1)
  assert.equal(timer.size(), 0)
  await queue.schedule()
})
