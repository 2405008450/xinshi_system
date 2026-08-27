/**
 * 角色权限配置
 * - admin / 超级管理员：可访问所有菜单与路由
 * - 客户专员、项目专员、项目经理：仅可访问「项目管理」下的「笔译项目管理」
 */

export const ROLE_ADMIN = 'admin'
export const ROLE_SUPER_ADMIN = '超级管理员'
export const ROLE_CUSTOMER_SPECIALIST = '客户专员'
export const ROLE_PROJECT_SPECIALIST = '项目专员'
export const ROLE_PROJECT_MANAGER = '项目经理'
export const ROLE_TEST = '测试'
export const ROLE_REVIEW = '译审'
export const ROLE_SALES = '销售'

/** 拥有全部权限的角色（任一即可） */
export const SUPER_ROLES = [ROLE_ADMIN, ROLE_SUPER_ADMIN]

/**
 * 从 localStorage 读取当前用户角色列表
 * @returns {string[]}
 */
export function getStoredRoles() {
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
  try {
    const raw = localStorage.getItem('user_permissions')
    if (!raw) return []
    const list = JSON.parse(raw)
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
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
  if (hasPermission('schedule:read')) return '/work-schedule'
  if (hasPermission('clients:read')) return '/clients'
  if (hasPermission(['talents:read', 'translators:read'])) return '/resource-management/talents'
  if (hasPermission('finance:read')) return '/finance'
  return '/pending-modules'
}

/**
 * 路由 meta.roles：未配置或空数组表示仅超级管理员可访问
 * 配置了角色列表表示：超级管理员 或 拥有列表中任一角色的用户 可访问
 * @param {import('vue-router').RouteLocationNormalized} route
 * @returns {boolean}
 */
export function canAccessRoute(route) {
  const userRoles = getStoredRoles()
  if (isSuperAdmin(userRoles)) return true

  const metaPermissions = route.meta?.permissions
  if (metaPermissions?.length) {
    return hasPermission(metaPermissions)
  }

  const metaRoles = route.meta?.roles
  if (!metaRoles || metaRoles.length === 0) return false
  if (metaRoles.includes('*')) return true

  return metaRoles.some((r) => userRoles.includes(r))
}

/**
 * 笔译项目管理相关路由/路径（扁平，用于菜单与守卫）
 * 所有普通员工（非超级管理员）均可访问这些基本功能
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
