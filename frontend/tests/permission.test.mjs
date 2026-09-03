import test from 'node:test'
import assert from 'node:assert/strict'

import {
  canAccessRoute,
  canViewManuscriptArrangements,
  getDefaultRoute,
  hasPermission,
  setStoredAccess,
} from '../src/utils/permission.js'
import { computed } from 'vue'

const values = new Map()
globalThis.localStorage = {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, String(value)),
  removeItem: key => values.delete(key),
}

function setAccess(roles = [], permissions = []) {
  localStorage.setItem('user_roles', JSON.stringify(roles))
  localStorage.setItem('user_permissions', JSON.stringify(permissions))
}

test('项目路由由角色页配置的读取权限控制', () => {
  setAccess(['项目专员'], [])
  assert.equal(canAccessRoute({ meta: { permissions: ['projects:read'] } }), false)

  setAccess(['项目专员'], ['projects:read'])
  assert.equal(canAccessRoute({ meta: { permissions: ['projects:read'] } }), true)
})

test('权限数组内部按任一权限放行标注工作区', () => {
  setAccess(['测试'], ['annotation_accounts:read'])
  assert.equal(canAccessRoute({
    meta: { permissions: ['projects:read', 'annotation_accounts:read', 'annotation_accounts:write'] },
  }), true)
})

test('稿件安排同时校验项目读取权限和指定角色', () => {
  setAccess(['项目经理'], [])
  assert.equal(canViewManuscriptArrangements(), false)
  assert.equal(canAccessRoute({
    meta: { permissions: ['projects:read'], roles: ['项目经理', '项目助理'] },
  }), false)

  setAccess(['项目经理'], ['projects:read'])
  assert.equal(canViewManuscriptArrangements(), true)
  assert.equal(canAccessRoute({
    meta: { permissions: ['projects:read'], roles: ['项目经理', '项目助理'] },
  }), true)

  setAccess(['项目专员'], ['projects:read'])
  assert.equal(canViewManuscriptArrangements(), false)
})

test('仅有招聘人才读取权限时默认进入可访问的资源页', () => {
  setAccess(['招聘'], ['recruitment_talents:read'])
  assert.equal(getDefaultRoute(), '/resource-management/recruitment-talents')
})

test('会话权限同步后依赖权限的导航状态立即更新', () => {
  setStoredAccess(['测试'], [])
  const canViewProjects = computed(() => hasPermission('projects:read'))
  assert.equal(canViewProjects.value, false)

  setStoredAccess(['测试'], ['projects:read'])
  assert.equal(canViewProjects.value, true)
})
