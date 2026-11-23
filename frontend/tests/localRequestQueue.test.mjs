import test from 'node:test'
import assert from 'node:assert/strict'
import { createLocalRequestQueue } from '../src/utils/localRequestQueue.js'

function lockManager() {
  const tails = new Map()
  return { request(name, options, callback) {
    const previous = tails.get(name) || Promise.resolve()
    const current = previous.catch(() => {}).then(() => {
      if (options.signal?.aborted) throw Object.assign(new Error(), { name: 'AbortError' })
      return callback()
    })
    tails.set(name, current)
    return current
  } }
}
const canceledError = () => Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' })

test('localhost tabs share two business slots and keep authentication independent', async () => {
  const locks = lockManager()
  const tabs = Array.from({ length: 3 }, () => createLocalRequestQueue({ locks, hostname: 'localhost', canceledError }))
  let active = 0, peak = 0
  const release = []
  const send = () => { active++; peak = Math.max(peak, active); return new Promise(resolve => release.push(() => { active--; resolve('ok') })) }
  const pending = tabs.flatMap(queue => Array.from({ length: 4 }, () => queue({ url: '/projects' }, send)))
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(active, 2)
  assert.equal(await tabs[0]({ url: '/auth/session' }, async () => 'session'), 'session')
  while (release.length || active) {
    release.splice(0).forEach(resolve => resolve())
    await new Promise(resolve => setImmediate(resolve))
  }
  assert.equal((await Promise.all(pending)).length, 12)
  assert.equal(peak, 2)
})

test('canceled queued queries never send; failures release slots', async () => {
  const queue = createLocalRequestQueue({ locks: lockManager(), hostname: 'localhost', canceledError, slots: 1 })
  let release
  const first = queue({ url: '/projects' }, () => new Promise(resolve => { release = resolve }))
  await new Promise(resolve => setImmediate(resolve))
  const controller = new AbortController()
  const second = queue({ url: '/projects', signal: controller.signal }, () => assert.fail('canceled request sent'))
  const canceled = assert.rejects(second, { code: 'ERR_CANCELED' })
  controller.abort(); release()
  await Promise.all([first, canceled])
  await assert.rejects(queue({ url: '/projects' }, async () => { throw new Error('failed') }), /failed/)
  assert.equal(await queue({ url: '/projects' }, async () => 'recovered'), 'recovered')
})

test('OA requests and browsers without Web Locks keep their existing transport', async () => {
  for (const options of [{ hostname: 'oa.example', locks: { request() { assert.fail() } } }, { hostname: 'localhost' }]) {
    const queue = createLocalRequestQueue({ ...options, canceledError })
    assert.equal(await queue({}, async () => 'ok'), 'ok')
  }
})

test('only explicitly retryable local reads retry, with a bounded number of attempts', async () => {
  const delays = []
  const queue = createLocalRequestQueue({ hostname: 'localhost', canceledError, pause: async delay => delays.push(delay) })
  const busy = { response: { status: 503, headers: { 'retry-after': '1' } } }
  let calls = 0
  assert.equal(await queue({ method: 'get' }, async () => { if (++calls < 3) throw busy; return 'ok' }), 'ok')
  assert.equal(calls, 3)
  assert.deepEqual(delays, [1000, 1000])
  calls = 0
  await assert.rejects(queue({ method: 'get' }, async () => { calls++; throw busy }))
  assert.equal(calls, 3)
  for (const [config, error] of [[{ method: 'post' }, busy], [{ method: 'get' }, { response: { status: 503 } }],
    [{ method: 'get' }, { response: { status: 500 } }], [{ method: 'get' }, new Error('timeout')]]) {
    calls = 0
    await assert.rejects(queue(config, async () => { calls++; throw error }))
    assert.equal(calls, 1)
  }
})

test('canceling a delayed read stops retries', async () => {
  const controller = new AbortController()
  let calls = 0
  const queue = createLocalRequestQueue({ hostname: 'localhost', canceledError,
    pause: async () => { controller.abort(); throw canceledError() } })
  await assert.rejects(queue({ method: 'get', signal: controller.signal }, async () => {
    calls++; throw { response: { status: 503, headers: { 'retry-after': '1' } } }
  }), { code: 'ERR_CANCELED' })
  assert.equal(calls, 1)
})
