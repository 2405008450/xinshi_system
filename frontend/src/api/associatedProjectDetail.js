import { getAnnotationProject } from './annotationProjects'
import { getProject } from './projects'
import { getInterpretationProject } from './interpretationProjects'
import { getRecruitmentProject } from './recruitmentProjects'
import { getStatusHistory, getCustomFields } from './annotationOps'
import { listMaterials } from './annotationMaterials'

const loaders = { annotation: getAnnotationProject, translation: getProject, interpretation: getInterpretationProject, recruitment: getRecruitmentProject }

export async function fetchAssociatedProject({ sourceType, projectId }, signal) {
  const detail = await loaders[sourceType](projectId, { signal })
  if (signal.aborted) throw new DOMException('请求已取消', 'AbortError')
  if (sourceType !== 'annotation') return { detail }
  const results = await Promise.allSettled([
    getStatusHistory(projectId, { signal }), getCustomFields('project', null, false, { signal }), listMaterials(projectId, { signal }),
  ])
  const names = ['状态履历', '自定义字段', '云端项目资料']
  const warnings = results.flatMap((result, index) => result.status === 'rejected' ? [`${names[index]}加载失败或无查看权限，可重试或进入项目查看`] : [])
  return { detail, history: results[0].value || [], customFields: results[1].value || [], materials: results[2].value || [], materialsError: results[2].status === 'rejected' ? '云端项目资料加载失败或无查看权限' : '', warnings }
}
