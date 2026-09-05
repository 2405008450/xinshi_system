/**
 * 流程相关 API（按角色获取用户等）
 * 用于「完成并提交」时选择下一环节指定用户
 */
import { getRoles } from './roles'
import { getUserRolesByRole } from './userRoles'
import { getUsers } from './users'
import api from './index'

// ===== 母订单工作流 =====
export const getWorkflowConfigAPI = () => api.get('/workflow/config')
export const getMyTasksAPI = () => api.get('/workflow/my-tasks')
export const getManagementProjectsAPI = () => api.get('/workflow/management-projects')
const projectRefs = (projects) => projects.map(item => ({
  project_type: item.project_type || 'translation',
  project_id: item.project_id || item.translation_project_id
}))
const workItemRefs = (items) => items.map(item => ({
  source_kind: item.source_kind || 'translation_workflow',
  source_id: item.project_responsibility_id || item.workflow_instance_id || item.source_id
}))

export const claimManagementProjectsAPI = (projects) =>
  api.post('/workflow/project-manager-claim', { project_refs: projectRefs(projects) })
export const getProjectManagerCandidatesAPI = (params = {}) => api.get('/workflow/project-manager-candidates', { params })
export const getProjectEditorOptionsAPI = () => api.get('/workflow/project-editor-options')
export const getProjectRoleCandidatesAPI = (roleCode) =>
  api.get(`/workflow/role-candidates/${encodeURIComponent(roleCode)}`)
export const createProjectManagerHandoverAPI = (data) => api.post('/workflow/project-manager-handover', data)
export const getIncomingProjectManagerHandoversAPI = () => api.get('/workflow/project-manager-handover/incoming')
export const acceptProjectManagerHandoverAPI = (requestId, data = {}) =>
  api.post(`/workflow/project-manager-handover/${requestId}/accept`, data)
export const rejectProjectManagerHandoverAPI = (requestId, data = {}) =>
  api.post(`/workflow/project-manager-handover/${requestId}/reject`, data)
export const getTransferableTasksAPI = (params = {}, config = {}) =>
  api.get('/workflow/transferable-tasks', { params, ...config })
export const getEligibleTransferUsersAPI = (items) =>
  api.post('/workflow/eligible-users', { work_item_refs: workItemRefs(items) })
export const handoverWorkflowTasksAPI = (data) => api.post('/workflow/handover', {
  ...data,
  work_item_refs: data.items ? workItemRefs(data.items) : data.work_item_refs
})
export const claimWorkflowTasksAPI = (data) => api.post('/workflow/claim', {
  ...data,
  work_item_refs: data.items ? workItemRefs(data.items) : data.work_item_refs
})
export const claimRolePoolTasksAPI = (items) =>
  api.post('/workflow/role-pool-claim', { work_item_refs: workItemRefs(items) })
export const getIncomingHandoverRequestsAPI = () => api.get('/workflow/handover-requests/incoming')
export const acceptHandoverRequestAPI = (requestId, data = {}) =>
  api.post(`/workflow/handover-requests/${requestId}/accept`, data)
export const rejectHandoverRequestAPI = (requestId, data = {}) =>
  api.post(`/workflow/handover-requests/${requestId}/reject`, data)
export const returnDelegatedTasksAPI = (delegationIds, note = '') =>
  api.post('/workflow/delegations/return', { delegation_ids: delegationIds, note: note || undefined })
export const getWorkflowStateAPI = (projectId) => api.get(`/workflow/${projectId}`)
export const initWorkflowAPI = (projectId) => api.post(`/workflow/${projectId}/init`)
export const setDifficultyAPI = (projectId, data) => api.post(`/workflow/${projectId}/set-difficulty`, data)
export const transitionWorkflowAPI = (projectId, data) => api.post(`/workflow/${projectId}/transition`, data)
export const rollbackWorkflowAPI = (projectId, data) => api.post(`/workflow/${projectId}/rollback`, data)
export const updateStageDataAPI = (projectId, data) => api.put(`/workflow/${projectId}/stage-data`, data)

// ===== 子订单工作流 =====
export const getSubOrderWorkflowStateAPI = (subOrderId) => api.get(`/workflow/suborder/${subOrderId}`)
export const initSubOrderWorkflowAPI = (subOrderId) => api.post(`/workflow/suborder/${subOrderId}/init`)
export const setSubOrderDifficultyAPI = (subOrderId, data) => api.post(`/workflow/suborder/${subOrderId}/set-difficulty`, data)
export const transitionSubOrderWorkflowAPI = (subOrderId, data) => api.post(`/workflow/suborder/${subOrderId}/transition`, data)
export const rollbackSubOrderWorkflowAPI = (subOrderId, data) => api.post(`/workflow/suborder/${subOrderId}/rollback`, data)
export const updateSubOrderStageDataAPI = (subOrderId, data) => api.put(`/workflow/suborder/${subOrderId}/stage-data`, data)

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
  const allUsers = await getUsers({ limit: 500, include_leave_status: true })
  const list = Array.isArray(allUsers) ? allUsers : []
  return list.filter((u) => u && userIds.has(String(u.id)))
}
