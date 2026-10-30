import test from 'node:test'
import assert from 'node:assert/strict'

import {
  canAccessRoute,
  canManageDepartments,
  canConfigureWorkReports,
  canViewManuscriptArrangements,
  canViewTalentResourceLibrary,
  getDefaultRoute,
  hasPermission,
  setStoredAccess,
} from '../src/utils/permission.js'
import { computed } from 'vue'
import { technicalDevelopmentAccess } from '../src/utils/technicalDevelopmentAccess.js'

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

test('人才资源库对所有已登录角色开放', () => {
  setAccess(['招聘'], ['recruitment_talents:read'])
  assert.equal(canViewTalentResourceLibrary(), true)
  assert.equal(canAccessRoute({
    meta: { roles: ['*'] },
  }), true)
  assert.equal(getDefaultRoute(), '/resource-management/talent-overview')

  setAccess(['项目专员'], [])
  assert.equal(canViewTalentResourceLibrary(), true)
  assert.equal(getDefaultRoute(), '/resource-management/talent-overview')

  setAccess(['超级管理员'], [])
  assert.equal(canViewTalentResourceLibrary(), true)
  assert.equal(canAccessRoute({
    meta: { roles: ['*'] },
  }), true)
})

test('会话权限同步后依赖权限的导航状态立即更新', () => {
  setStoredAccess(['测试'], [])
  const canViewProjects = computed(() => hasPermission('projects:read'))
  assert.equal(canViewProjects.value, false)

  setStoredAccess(['测试'], ['projects:read'])
  assert.equal(canViewProjects.value, true)
})

test('修改订单号权限独立于普通项目编辑权限', () => {
  setAccess(['测试'], ['projects:write'])
  assert.equal(hasPermission('projects:order_no:write'), false)

  setAccess(['测试'], ['projects:write', 'projects:order_no:write'])
  assert.equal(hasPermission('projects:order_no:write'), true)
})


test('行政组织权限开放组织架构但不扩大角色及用户系统管理权限', () => {
  localStorage.setItem('user_name', 'administration-person')
  setStoredAccess([], ['system:users:read', 'system:organization:write'])
  assert.equal(canManageDepartments(), true)
  assert.equal(canConfigureWorkReports(), true)
  assert.equal(canAccessRoute({meta:{organizationManagement:true}}), true)
  assert.equal(hasPermission('system:users:write'), false)
  assert.equal(hasPermission('system:user_roles:write'), false)
  assert.equal(hasPermission('system:roles:write'), false)
  setStoredAccess([], [])
  assert.equal(canManageDepartments(), false)
  assert.equal(canConfigureWorkReports(), false)
  assert.equal(canAccessRoute({meta:{organizationManagement:true}}), false)
})


test('组织架构迁入人事管理后沿用组织权限，不能借此访问排班考勤', () => {
  localStorage.setItem('user_name', 'organization-viewer')
  setStoredAccess([], ['system:users:read'])
  assert.equal(canAccessRoute({meta:{hrManagement:true,organizationManagement:true}}), true)
  assert.equal(canAccessRoute({meta:{hrManagement:true}}), false)
  assert.equal(getDefaultRoute(), '/hr-management/organization')
})

test('技术管理仅按服务器确认的本人部门权限放行，超级管理员无额外通道', () => {
  localStorage.setItem('user_id', 'technical-user')
  setAccess(['超级管理员'], ['*'])
  Object.assign(technicalDevelopmentAccess, { userId: 'technical-user', can_enter: false })
  assert.equal(canAccessRoute({ meta: { technicalDevelopment: true } }), false)
  technicalDevelopmentAccess.can_enter = true
  assert.equal(canAccessRoute({ meta: { technicalDevelopment: true } }), true)
  localStorage.setItem('user_id', 'other-user')
  assert.equal(canAccessRoute({ meta: { technicalDevelopment: true } }), false)
  localStorage.removeItem('user_id')
})
