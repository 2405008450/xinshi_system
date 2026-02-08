/**
 * 流程相关 API（按角色获取用户等）
 * 用于「完成并提交」时选择下一环节指定用户
 */
import { getRoles } from './roles'
import { getUserRolesByRole } from './userRoles'
import { getUsers } from './users'

/**
 * 按角色名称获取该角色下的用户列表（用于下一环节负责人选择）
 * @param {string} roleName 角色名称，如 '客户专员'、'项目经理'、'项目专员'
 * @returns {Promise<Array<{ id: string, username: string, full_name?: string }>>}
 */
export async function getUsersByRoleName(roleName) {
  const roles = await getRoles()
  const role = Array.isArray(roles) ? roles.find((r) => r.role_name === roleName) : null
  if (!role || !role.id) return []
  const userRoles = await getUserRolesByRole(role.id)
  const userIds = new Set((userRoles || []).map((ur) => String(ur.user_id)).filter(Boolean))
  if (userIds.size === 0) return []
  const allUsers = await getUsers({ limit: 500 })
  const list = Array.isArray(allUsers) ? allUsers : []
  return list.filter((u) => u && userIds.has(String(u.id)))
}
