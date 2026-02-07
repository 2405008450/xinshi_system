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
 * 路由 meta.roles：未配置或空数组表示仅超级管理员可访问
 * 配置了角色列表表示：超级管理员 或 拥有列表中任一角色的用户 可访问
 * @param {import('vue-router').RouteLocationNormalized} route
 * @returns {boolean}
 */
export function canAccessRoute(route) {
  const userRoles = getStoredRoles()
  if (isSuperAdmin(userRoles)) return true

  const metaRoles = route.meta?.roles
  if (!metaRoles || metaRoles.length === 0) return false
  return metaRoles.some((r) => userRoles.includes(r))
}

/**
 * 笔译项目管理相关路由/路径（用于菜单与守卫）
 * 客户专员、项目专员、项目经理 仅能访问这些
 */
export const TRANSLATION_PROJECT_PATHS = [
  '/project-management',
  '/project-management/translation',
  '/project-management/translation/project-details',
  '/project-management/translation/project-files'
]

/** 笔译项目管理可访问的角色（非超级管理员时）；含测试、译审、销售等，登录后均可进入默认页 */
export const TRANSLATION_PROJECT_ROLES = [
  ROLE_CUSTOMER_SPECIALIST,
  ROLE_PROJECT_SPECIALIST,
  ROLE_PROJECT_MANAGER,
  ROLE_TEST,
  ROLE_REVIEW,
  ROLE_SALES
]

/** 工作安排可访问的角色（含测试、译审、销售等，均可查看及「我的任务」） */
export const WORK_SCHEDULE_ROLES = [
  ROLE_SUPER_ADMIN,
  ROLE_ADMIN,
  ROLE_PROJECT_MANAGER,
  ROLE_CUSTOMER_SPECIALIST,
  ROLE_PROJECT_SPECIALIST,
  ROLE_TEST,
  ROLE_REVIEW,
  ROLE_SALES
]
