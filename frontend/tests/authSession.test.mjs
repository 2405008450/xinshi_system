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
