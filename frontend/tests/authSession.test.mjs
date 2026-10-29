import test from 'node:test'
import assert from 'node:assert/strict'
import { clearAuthSession } from '../src/utils/authSession.js'

test('退出或改密清除全部鉴权信息，同时保留个人偏好', () => {
  const keys = ['token', 'user_roles', 'user_permissions', 'user_name', 'user_id', 'user_full_name']
  const state = new Map([...keys.map(key => [key, 'old-session']), ['columns:profile:user', 'preference']])
  clearAuthSession({ removeItem: key => state.delete(key) })
  assert.deepEqual([...state.entries()], [['columns:profile:user', 'preference']])
  clearAuthSession({ removeItem: key => state.delete(key) })
  assert.equal(state.size, 1)
})

test('清除凭证之前通知在线检测释放当前电脑页面', () => {
  const previous = globalThis.window, events = []
  const values = new Map([['token', 'isolated-token'], ['user_id', 'qa']])
  const storage = { getItem: key => values.get(key), removeItem: key => values.delete(key) }
  globalThis.window = { localStorage: storage, dispatchEvent: event => events.push({ type: event.type, hasToken: values.has('token') }) }
  try {
    clearAuthSession(storage)
    assert.deepEqual(events, [{ type: 'auth-session-clearing', hasToken: true }])
    assert.equal(values.size, 0)
  } finally {
    if (previous === undefined) delete globalThis.window
    else globalThis.window = previous
  }
})
