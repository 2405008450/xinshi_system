import test from 'node:test'
import assert from 'node:assert/strict'
import { createSessionPermissionSync } from '../src/utils/sessionPermissionSync.js'

function setup({ fetchSession, cached = true } = {}) {
  let clock = 1_000_000, fetches = 0; const applied = []
  const sync = createSessionPermissionSync({
    getToken: () => 'token',
    fetchSession: async () => { fetches++; return fetchSession() },
    apply: session => applied.push(session), hasCachedSession: () => cached, now: () => clock,
  })
  return { sync, applied, fetches: () => fetches, advance: ms => { clock += ms } }
}

test('校验成功后 60 秒内跳转不再请求', async () => {
  const ctx = setup({ fetchSession: () => ({ user_id: 'u' }) })
  assert.equal(await ctx.sync(), true); assert.equal(await ctx.sync(), true)
  assert.equal(ctx.fetches(), 1); assert.equal(ctx.applied.length, 1)
  ctx.advance(61_000); await ctx.sync(); assert.equal(ctx.fetches(), 2)
})

test('401 和 403 视为未登录', async () => {
  for (const status of [401, 403]) {
    const ctx = setup({ fetchSession: () => { throw { response: { status } } } })
    assert.equal(await ctx.sync(), false)
  }
})

test('超时、网络中断和 503 在已有本地会话时放行，并在约 10 秒后重试', async () => {
  for (const error of [{ code: 'ECONNABORTED' }, { code: 'ERR_NETWORK' }, { response: { status: 503 } }, { response: { status: 502 } }]) {
    let fail = true
    const ctx = setup({ fetchSession: () => { if (fail) throw error; return { user_id: 'u' } } })
    assert.equal(await ctx.sync(), true); assert.equal(ctx.applied.length, 0)
    assert.equal(await ctx.sync(), true); assert.equal(ctx.fetches(), 1)
    ctx.advance(10_001); fail = false
    assert.equal(await ctx.sync(), true); assert.equal(ctx.fetches(), 2); assert.equal(ctx.applied.length, 1)
  }
})

test('没有本地会话时临时故障不放行', async () => {
  const ctx = setup({ cached: false, fetchSession: () => { throw { code: 'ECONNABORTED' } } })
  assert.equal(await ctx.sync(), null)
})

test('并发的校验共用同一次请求，强制校验仍会重新请求', async () => {
  let release; const ctx = setup({ fetchSession: () => new Promise(done => { release = done }) })
  const first = ctx.sync(), second = ctx.sync(true)
  await Promise.resolve(); release({ user_id: 'u' })
  assert.deepEqual(await Promise.all([first, second]), [true, true]); assert.equal(ctx.fetches(), 1)
  const forced = ctx.sync(true); await Promise.resolve(); release({ user_id: 'u' }); await forced
  assert.equal(ctx.fetches(), 2)
})

test('concurrent navigation shares validation and token changes invalidate cached permissions', async () => {
  let token = 'first', calls = 0, applied = 0, resolve
  const sync = createSessionPermissionSync({ getToken: () => token, fetchSession: () => { calls++; return new Promise(r => { resolve = r }) }, apply: () => { applied++ }, hasCachedSession: () => true })
  const first = sync(), second = sync()
  assert.equal(calls, 1)
  resolve({})
  assert.deepEqual(await Promise.all([first, second]), [true, true])
  assert.equal(await sync(), true)
  assert.equal(calls, 1)
  token = 'second'
  const changed = sync()
  assert.equal(calls, 2)
  token = 'third'
  resolve({})
  assert.equal(await changed, null)
  assert.equal(applied, 1)
})
