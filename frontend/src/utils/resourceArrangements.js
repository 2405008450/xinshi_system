import { formatBusinessDateTime } from './dateTime.js'

export const arrangementTargetKey = target => [target.kind, target.request_id || '', target.language_id || ''].join(':')
export const arrangementProjectKey = project => `${project.source_type}:${project.project_id}`
export const arrangementProjectTypes = [
  { value: 'annotation', label: '标注（含子订单）' }, { value: 'translation', label: '笔译' },
  { value: 'interpretation', label: '口译' }, { value: 'recruitment', label: '招聘' },
]
export const arrangementToday = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date())
export const arrangementChineseDate = value => new Date(`${value}T00:00:00+08:00`).toLocaleDateString('zh-CN', { timeZone:'Asia/Hong_Kong' })
export const arrangementChineseTime = formatBusinessDateTime
export const arrangementCellPayload = cell => ({
  platform_id: cell.platform_id, owner_id: cell.owner_id || null,
  targets: (cell.targets || []).map(t => ({ kind: t.kind, request_id: t.request_id || null, language_id: t.language_id || null })),
  role_tags: normalizeArrangementRoles(cell.role_tags),
  projects: (cell.manual_projects || []).map(p => ({ source_type: p.source_type, project_id: p.project_id })),
  remarks: cell.remarks || '',
})
export const normalizeArrangementRoles = tags => [...new Set((tags || []).map(tag => tag.trim()).filter(Boolean))]
export const arrangementCellChanged = (cell, previous) => JSON.stringify(arrangementCellPayload(cell)) !== JSON.stringify(arrangementCellPayload(previous || { platform_id: cell.platform_id }))
export function arrangementProjectRoute(project) {
  const names = { annotation: project.parent_project_id ? 'AnnotationChildOrders' : 'AnnotationProjectDetails',
    translation: 'TranslationProjectDetails', interpretation: 'InterpretationProjectDetails', recruitment: 'RecruitmentProjectDetails' }
  return { name: names[project.source_type], query: { projectId: project.project_id,
    ...(project.parent_project_id ? { parentProjectId: project.parent_project_id } : {}) } }
}
