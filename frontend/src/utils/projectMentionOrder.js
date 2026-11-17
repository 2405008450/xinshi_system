import { managerIds } from './annotationManagerChange.js'

export function projectMentionOrder(users, project) {
  if (!project) return users
  const projectManagers = managerIds(project, 'project_manager')
  if (!project?.roleAssignments && project?.projectManagerId) projectManagers.push(project.projectManagerId)
  const ranks = new Map()
  for (const [index, [ids, section]] of [
    [projectManagers, '项目经理'], [managerIds(project, 'client_manager'), '客户经理'],
  ].entries()) {
    for (const id of ids) if (!ranks.has(String(id))) ranks.set(String(id), { rank: index, section })
  }
  const seen = new Set()
  return users.filter(user => {
    const id = String(user.id)
    if (seen.has(id)) return false
    seen.add(id); return true
  }).map((user, index) => ({ ...user, index, rank: user.outside ? 4 : (ranks.get(String(user.id))?.rank ?? (user.all ? 2 : 3)),
    mentionSection: user.outside ? '群外人员 · 发送后邀请入群' : (ranks.get(String(user.id))?.section || (user.all ? '群组提醒' : '本群成员')),
  })).sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map(({ rank, index, ...user }) => user)
}
