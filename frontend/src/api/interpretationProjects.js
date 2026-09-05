import api from './index'
import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'
import { invalidateOptionCache } from '@/utils/optionCache'

const projectCreateState = { key: '', signature: '' }

const toCamelCase = (value) => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const toSnakeCase = (value) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)

const convertKeys = (value, converter) => {
  if (Array.isArray(value)) return value.map((item) => convertKeys(item, converter))
  if (value && value.constructor === Object) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [converter(key), convertKeys(item, converter)])
    )
  }
  return value
}

export const getInterpretationProjects = (params, config = {}) => (
  api.get('/projects/interpretation/', { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const getInterpretationProjectCount = (params, config = {}) => (
  api.get('/projects/interpretation/count', { ...config, params })
)

export const getInterpretationProjectPage = (params, config = {}) => (
  api.get('/projects/interpretation/page', { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const getInterpretationProject = (id) => (
  api.get(`/projects/interpretation/${id}`).then((res) => convertKeys(res, toCamelCase))
)

export const createInterpretationProject = async (data, idempotencyKey) => {
  const payload = convertKeys(data, toSnakeCase)
  const key = resolveIdempotencyKey(projectCreateState, payload, idempotencyKey)
  const response = await api.post('/projects/interpretation/', payload, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(projectCreateState, key)
  invalidateOptionCache('source-projects:interpretation:')
  return convertKeys(response, toCamelCase)
}

export const updateInterpretationProject = (id, data) => (
  api.put(`/projects/interpretation/${id}`, convertKeys(data, toSnakeCase)).then((res) => {
    invalidateOptionCache('source-projects:interpretation:')
    return convertKeys(res, toCamelCase)
  })
)

export const updateInterpretationProjectTextField = (id, field, value, expectedUpdatedAt) => (
  api.patch(`/projects/interpretation/${id}/text-field`, {
    field: toSnakeCase(field), value, expected_updated_at: expectedUpdatedAt,
  }).then((res) => convertKeys(res, toCamelCase))
)

export const updateInterpretationProjectStatus = (id, projectStatus) => (
  api.patch(`/projects/interpretation/${id}/status`, { project_status: projectStatus })
    .then((res) => convertKeys(res, toCamelCase))
)

export const deleteInterpretationProject = (id) => api.delete(`/projects/interpretation/${id}`).then((res) => {
  invalidateOptionCache('source-projects:interpretation:')
  return res
})

export const getInterpretationLanguages = (params = {}) => (
  api.get('/projects/interpretation/languages', { params }).then((res) => convertKeys(res, toCamelCase))
)

export const createInterpretationLanguage = (label) => (
  api.post('/projects/interpretation/languages', { label }).then((res) => convertKeys(res, toCamelCase))
)

export const updateInterpretationLanguage = (id, data) => (
  api.patch(`/projects/interpretation/languages/${id}`, convertKeys(data, toSnakeCase))
    .then((res) => convertKeys(res, toCamelCase))
)

export const previewInterpretationProjectName = (data) => (
  api.post('/projects/interpretation/name-preview', convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)
