/**
 * 判断任务是否来自当前用户可认领的角色池。
 */
export function isRolePoolWorkItem(item) {
  return !item?.current_assignee_id && (
    item?.assignment_type === 'role_pool' || !!item?.group_assign_role
  )
}

/**
 * 工作台“我的任务”的默认展示范围。
 *
 * 管理员接口会额外返回全局查看任务，这些任务仅在用户主动点击
 * “显示全部任务”后展示，不应计入默认任务数。
 */
export function isDefaultVisibleWorkItem(item, currentUserId = '') {
  if (isRolePoolWorkItem(item)) return true
  if (item?.current_assignee_id && currentUserId) {
    return String(item.current_assignee_id) === String(currentUserId)
  }
  return ['direct', 'project_role', 'delegated_out'].includes(item?.assignment_type)
}
