import test from 'node:test'
import assert from 'node:assert/strict'
import { clearAuthSession } from '../src/utils/authSession.js'

test('退出或改密清除全部鉴权信息，同时保留个人偏好', () => {
  const keys = ['token', 'user_roles', 'user_permissions', 'user_name', 'user_id', 'user_full_name']
  const preserved = [
    ['columns:profile:user', 'preference'],
    ['form-drafts:projects:old-session', 'create draft'],
    ['workbench-filters:my-tasks:other-user', 'other account'],
  ]
  const state = new Map([
    ...keys.map(key => [key, 'old-session']),
    ['workbench-filters:my-tasks:old-session', 'filters'],
    ['workbench-filters:management-projects:old-session', 'filters'],
    ...preserved,
  ])
  const storage = { getItem: key => state.get(key), removeItem: key => state.delete(key) }
  clearAuthSession(storage)
  assert.deepEqual([...state.entries()], preserved)
  clearAuthSession(storage)
  assert.deepEqual([...state.entries()], preserved)
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
