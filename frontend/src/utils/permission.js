/**
 * 角色权限配置
 * - admin / 超级管理员：可访问所有菜单与路由
 * - 普通角色：按角色管理中配置的权限访问菜单、路由和操作
 */

import { ref } from 'vue'

export const ROLE_ADMIN = 'admin'
export const ROLE_SUPER_ADMIN = '超级管理员'
export const ROLE_CUSTOMER_SPECIALIST = '客户专员'
export const ROLE_PROJECT_SPECIALIST = '项目专员'
export const ROLE_PROJECT_MANAGER = '项目经理'
export const ROLE_PROJECT_ASSISTANT = '项目助理'
export const ROLE_TEST = '测试'
export const ROLE_REVIEW = '译审'
export const ROLE_SALES = '销售'

/** 拥有全部权限的角色（任一即可） */
export const SUPER_ROLES = [ROLE_ADMIN, ROLE_SUPER_ADMIN]

// localStorage 本身不是响应式数据；会话同步后递增版本，使侧栏 computed 立即重算。
const storedAccessRevision = ref(0)

/** 可查看“稿件安排”的普通角色；超级管理员由 canAccessRoute 单独放行。 */
export const MANUSCRIPT_VIEW_ROLES = [ROLE_PROJECT_MANAGER, ROLE_PROJECT_ASSISTANT]

/**
 * 从 localStorage 读取当前用户角色列表
 * @returns {string[]}
 */
export function getStoredRoles() {
  storedAccessRevision.value
  try {
    const raw = localStorage.getItem('user_roles')
    if (!raw) return []
    const list = JSON.parse(raw)
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function getStoredPermissions() {
  storedAccessRevision.value
  try {
    const raw = localStorage.getItem('user_permissions')
    if (!raw) return []
    const list = JSON.parse(raw)
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

/** 写入登录用户的角色与权限，并通知依赖它们的导航和操作控件刷新。 */
export function setStoredAccess(roles, permissions) {
  localStorage.setItem('user_roles', JSON.stringify(Array.isArray(roles) ? roles : []))
  localStorage.setItem('user_permissions', JSON.stringify(Array.isArray(permissions) ? permissions : []))
  storedAccessRevision.value += 1
}

/**
 * 是否为超级管理员（拥有全部权限）
 * @param {string[]} [roles] 不传则从 localStorage 读
 */
export function isSuperAdmin(roles) {
  const r = roles ?? getStoredRoles()
  return r.some((role) => SUPER_ROLES.includes(role))
}

/**
 * 当前用户是否拥有指定角色之一
 * @param {string|string[]} roleOrRoles 单个角色或角色列表
 * @param {string[]} [userRoles] 不传则从 localStorage 读
 */
export function hasRole(roleOrRoles, userRoles) {
  const roles = getStoredRoles()
  const list = Array.isArray(roleOrRoles) ? roleOrRoles : [roleOrRoles]
  const target = userRoles ?? roles
  return list.some((r) => target.includes(r))
}

/** 是否允许查看“稿件安排”模块；与后端保持“项目读取权限 + 指定角色”的双重限制。 */
export function canViewManuscriptArrangements(userRoles, userPermissions) {
  const roles = userRoles ?? getStoredRoles()
  return isSuperAdmin(roles) || (
    hasRole(MANUSCRIPT_VIEW_ROLES, roles) &&
    hasPermission('projects:read', userPermissions)
  )
}

/**
 * 判断当前用户是否拥有指定权限之一。
 * `*` 由后端仅授予超级管理员。
 */
export function hasPermission(permissionOrPermissions, userPermissions) {
  // 兼容 RBAC 升级前已登录的超级管理员会话：
  // 旧会话没有 user_permissions，但已有超级管理员角色。
  if (isSuperAdmin()) return true
  const permissions = userPermissions ?? getStoredPermissions()
  if (permissions.includes('*')) return true
  const required = Array.isArray(permissionOrPermissions)
    ? permissionOrPermissions
    : [permissionOrPermissions]
  return required.some((permission) => permissions.includes(permission))
}

/**
 * 登录后和访问根路径时使用的默认页面。
 * 优先进入工作台，避免先跳固定地址后再由路由守卫二次重定向。
 */
export function getDefaultRoute() {
  if (isSuperAdmin() || hasPermission(['projects:read', 'tasks:read'])) return '/workbench'
  if (hasPermission(['annotation_accounts:read', 'annotation_accounts:write'])) return '/annotation-details?section=accounts'
  if (hasPermission('system:users:read')) return '/users'
  if (hasPermission('system:roles:read')) return '/roles'
  if (hasPermission('system:mail_settings:read')) return '/mail-settings'
  if (hasPermission('consultations:read')) return '/consultations'
  if (hasPermission('schedule:read')) return '/work-schedule'
  if (hasPermission('clients:read')) return '/clients'
  if (hasPermission(['talents:read', 'translators:read'])) return '/resource-management/talents'
  if (hasPermission('recruitment_talents:read')) return '/resource-management/recruitment-talents'
  if (hasPermission('finance:read')) return '/finance'
  return '/pending-modules'
}

/**
 * permissions 数组内部、roles 数组内部均为“满足任一项”；
 * 同一路由同时配置 permissions 与 roles 时，两类条件必须同时满足。
 * 两者均未配置时仅超级管理员可访问。
 * @param {import('vue-router').RouteLocationNormalized} route
 * @returns {boolean}
 */
export function canAccessRoute(route) {
  const userRoles = getStoredRoles()
  if (isSuperAdmin(userRoles)) return true

  const metaPermissions = route.meta?.permissions
  const metaRoles = route.meta?.roles
  const hasPermissionRule = Array.isArray(metaPermissions) && metaPermissions.length > 0
  const hasRoleRule = Array.isArray(metaRoles) && metaRoles.length > 0

  if (!hasPermissionRule && !hasRoleRule) return false

  const permissionAllowed = !hasPermissionRule || hasPermission(metaPermissions)
  const roleAllowed = !hasRoleRule || metaRoles.includes('*') || metaRoles.some((role) => userRoles.includes(role))
  return permissionAllowed && roleAllowed
}

/**
 * 笔译项目管理相关路由/路径（扁平，用于菜单与守卫）
 * 拥有 projects:read 的用户可访问这些基本功能
 */
export const TRANSLATION_PROJECT_PATHS = [
  '/translation',
  '/translation-details',
  '/interpretation-details',
  '/annotation-details',
  '/recruitment-details'
]

/** 排班管理编辑权限：仅项目经理与超级管理员可以编辑 */
export const SCHEDULE_ADMIN_ROLES = [
  ROLE_SUPER_ADMIN,
  ROLE_ADMIN,
  ROLE_PROJECT_MANAGER
]

/**
 * 判断当前用户是否有排班管理编辑权限
 * @returns {boolean}
 */
export function canEditSchedule() {
  return hasPermission('schedule:write')
}
