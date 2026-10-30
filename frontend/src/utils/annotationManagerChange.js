export const managerIds = (row, role) => role === 'client_manager'
  ? (row?.clientManagerId ? [row.clientManagerId] : [])
  : [...new Set((row?.roleAssignments || [])
      .filter(item => (item.roleCode || item.role_code) === 'project_manager')
      .map(item => item.assigneeId || item.assignee_id).filter(Boolean))]

export const sameManagers = (left, right) => left.length === right.length && left.every(id => right.includes(id))

export function managerChanges(before, after) {
  return ['client_manager', 'project_manager'].flatMap(role => {
    const previous = managerIds(before, role), next = managerIds(after, role)
    return sameManagers(previous, next) ? [] : [{
      role, label: role === 'client_manager' ? '客户经理' : '项目经理', previous, next,
      requiresReason: role === 'client_manager' || previous.length > 0 || Boolean(before?.managerAssignmentHistory?.[role]),
    }]
  })
}
