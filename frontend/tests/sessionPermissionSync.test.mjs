import test from 'node:test'
import assert from 'node:assert/strict'
import { createSessionPermissionSync } from '../src/utils/sessionPermissionSync.js'

test('temporary errors preserve session but do not approve unverified navigation', async () => {
  for (const error of [{ response: { status: 503 } }, { response: { status: 500 } }, new Error('timeout')]) {
    const sync = createSessionPermissionSync({ getToken: () => 'token', fetchSession: async () => { throw error }, applySession: () => assert.fail() })
    assert.equal(await sync(), null)
  }
  const sync = createSessionPermissionSync({ getToken: () => 'token', fetchSession: async () => { throw { response: { status: 401 } } }, applySession: () => assert.fail() })
  assert.equal(await sync(), false)
})

test('concurrent navigation shares validation and token changes invalidate cached permissions', async () => {
  let token = 'first', calls = 0, applied = 0, resolve
  const sync = createSessionPermissionSync({ getToken: () => token, fetchSession: () => { calls++; return new Promise(r => { resolve = r }) }, applySession: () => { applied++ } })
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
