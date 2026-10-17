const roleLabels = { project_manager: '项目经理', project_specialist: '项目专员', project_assistant: '项目助理' }

export const annotationInternalRolesText = (row) => {
  const roles = new Map()
  for (const item of row?.roleAssignments || []) {
    const key = item.roleCode || item.roleName
    if (!key) continue
    if (!roles.has(key)) roles.set(key, { label: roleLabels[key] || item.roleName || key, assignees: new Map() })
    // 兼容旧接口的重复空占位；实际负责人不能被“未分配”淹没。
    if (item.assigneeId || item.assigneeName) {
      roles.get(key).assignees.set(item.assigneeId || item.assigneeName, item.assigneeName || '姓名未提供')
    }
  }
  return [...roles.values()].map(({ label, assignees }) => `${label}：${assignees.size ? [...assignees.values()].join('、') : '未分配'}`).join('；') || '-'
}
