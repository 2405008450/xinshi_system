import { getProject } from '@/api/projects'
import { getInterpretationProject } from '@/api/interpretationProjects'
import { getAnnotationProject } from '@/api/annotationProjects'
import { getRecruitmentProject } from '@/api/recruitmentProjects'

export const projectTypeNames = { translation: '笔译项目', interpretation: '口译项目', annotation: '标注项目', recruitment: '招聘项目' }
export function resolveProjectType(value, orderNo = '') {
  if (projectTypeNames[value]) return value
  return Object.keys(projectTypeNames).find(key => projectTypeNames[key] === value) ||
    ({ TP: 'translation', IP: 'interpretation', AP: 'annotation', RP: 'recruitment' })[String(orderNo).split('-')[0]] || ''
}
export function loadProjectIdentity(type, id, config = {}) {
  const load = { translation: getProject, interpretation: getInterpretationProject, annotation: getAnnotationProject, recruitment: getRecruitmentProject }[type]
  return load ? load(id, config) : Promise.reject(new Error('未知项目类型'))
}
export function projectManagerNames(project = {}) {
  const names = (project.roleAssignments || []).filter(row => row.roleCode === 'project_manager').map(row => row.assigneeName).filter(Boolean)
  return [...new Set(names)].join('、') || project.projectManagerName || project.projectManager || '未设置'
}
