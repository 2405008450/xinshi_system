import api from './index'
import { clearIdempotencyKey, resetIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'

const projectCreateState = { key: '', signature: '' }
export const resetRecruitmentProjectIdempotency = () => resetIdempotencyKey(projectCreateState)

const toCamelCase = (value) => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const toSnakeCase = (value) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)

const convertKeys = (value, converter) => {
  if (Array.isArray(value)) return value.map((item) => convertKeys(item, converter))
  if (value && value.constructor === Object) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [converter(key), convertKeys(item, converter)]))
  }
  return value
}

const fromApi = (value) => convertKeys(value, toCamelCase)
const toApi = (value) => convertKeys(value, toSnakeCase)

export const getRecruitmentProjects = (params, config = {}) => (
  api.get('/projects/recruitment/', { ...config, params }).then(fromApi)
)
export const getRecruitmentProjectCount = (params, config = {}) => (
  api.get('/projects/recruitment/count', { ...config, params })
)
export const getRecruitmentProject = (id) => api.get(`/projects/recruitment/${id}`).then(fromApi)
export const createRecruitmentProject = async (data, idempotencyKey) => {
  const payload = toApi(data)
  const key = resolveIdempotencyKey(projectCreateState, payload, idempotencyKey)
  const response = await api.post('/projects/recruitment/', payload, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(projectCreateState, key)
  return fromApi(response)
}
export const updateRecruitmentProject = (id, data) => api.put(`/projects/recruitment/${id}`, toApi(data)).then(fromApi)
export const updateRecruitmentProjectTextField = (id, field, value, expectedUpdatedAt) => api.patch(`/projects/recruitment/${id}/text-field`, {
  field: toSnakeCase(field), value, expected_updated_at: expectedUpdatedAt,
}).then(fromApi)
export const patchRecruitmentProjectStatus = (id, projectStatus) => api.patch(`/projects/recruitment/${id}/status`, { project_status: projectStatus }).then(fromApi)
export const deleteRecruitmentProject = (id) => api.delete(`/projects/recruitment/${id}`)
export const previewRecruitmentProjectName = (data) => api.post('/projects/recruitment/name-preview', toApi(data)).then(fromApi)

export const getRecruitmentProgress = (projectId) => api.get(`/projects/recruitment/${projectId}/progress`).then(fromApi)
export const createRecruitmentProgress = (projectId, data) => api.post(`/projects/recruitment/${projectId}/progress`, toApi(data)).then(fromApi)

export const getRecruitmentCandidates = (projectId) => api.get(`/projects/recruitment/${projectId}/candidates`).then(fromApi)
export const createRecruitmentCandidate = (projectId, data) => api.post(`/projects/recruitment/${projectId}/candidates`, toApi(data)).then(fromApi)
export const updateRecruitmentCandidate = (candidateId, data) => api.put(`/projects/recruitment/candidate/${candidateId}`, toApi(data)).then(fromApi)
export const patchRecruitmentCandidate = (candidateId, data) => api.patch(`/projects/recruitment/candidate/${candidateId}`, toApi(data)).then(fromApi)
export const deleteRecruitmentCandidate = (candidateId) => api.delete(`/projects/recruitment/candidate/${candidateId}`)
export const getRecruitmentResumeSources = () => api.get('/projects/recruitment/resume-sources').then(fromApi)
export const createRecruitmentResumeSource = (label) => api.post('/projects/recruitment/resume-sources', { label }).then(fromApi)
export const createRecruitmentCandidateCommunication = (candidateId, data) => api.post(`/projects/recruitment/candidate/${candidateId}/communications`, toApi(data)).then(fromApi)
export const updateRecruitmentCandidateCommunication = (communicationId, data) => api.put(`/projects/recruitment/candidate/communication/${communicationId}`, toApi(data)).then(fromApi)
