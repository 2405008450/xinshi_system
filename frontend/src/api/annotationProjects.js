import api from './index'
import { clearIdempotencyKey, resetIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'
import { invalidateOptionCache } from '@/utils/optionCache'
import { convertAnnotationKeys as convertKeys } from '@/utils/annotationStatus'

const projectCreateState = { key: '', signature: '' }
export const resetAnnotationProjectIdempotency = () => resetIdempotencyKey(projectCreateState)

const toCamelCase = (value) => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const toSnakeCase = (value) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)

export const getAnnotationProjects = (params, config = {}) => (
  api.get('/projects/annotation/', { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const getAnnotationProjectCount = (params, config = {}) => (
  api.get('/projects/annotation/count', { ...config, params })
)

export const getAnnotationProjectPage = (params, config = {}) => (
  api.get('/projects/annotation/page', { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const getAnnotationProject = (id, config = {}) => (
  api.get(`/projects/annotation/${id}`, config).then((res) => convertKeys(res, toCamelCase))
)

export const getAnnotationChildren = (id, params = {}, config = {}) => (
  api.get(`/projects/annotation/${id}/children`, { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const createAnnotationChildren = (id, items, key, single = false) => (
  api.post(`/projects/annotation/${id}/children${single ? '' : '/batch'}`,
    convertKeys(single ? items[0] : { items }, toSnakeCase),
    { headers: { 'X-Idempotency-Key': key } },
  ).then((res) => {
    invalidateOptionCache('source-projects:annotation:')
    return convertKeys(res, toCamelCase)
  })
)

export const lookupAnnotationLanguageReserves = (languageIds) => (
  api.post('/projects/annotation/language-reserves/lookup', {
    language_ids: [...new Set(languageIds)].filter(Boolean),
  }).then((res) => convertKeys(res, toCamelCase))
)

export const createAnnotationProject = async (data, idempotencyKey) => {
  const payload = convertKeys(data, toSnakeCase)
  const key = resolveIdempotencyKey(projectCreateState, payload, idempotencyKey)
  const response = await api.post('/projects/annotation/', payload, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(projectCreateState, key)
  invalidateOptionCache('source-projects:annotation:')
  return convertKeys(response, toCamelCase)
}

export const updateAnnotationProject = (id, data) => (
  api.put(`/projects/annotation/${id}`, convertKeys(data, toSnakeCase)).then((res) => {
    invalidateOptionCache('source-projects:annotation:')
    return convertKeys(res, toCamelCase)
  })
)

export const updateAnnotationProjectTextField = (id, field, value, expectedUpdatedAt) => (
  api.patch(`/projects/annotation/${id}/text-field`, {
    field: toSnakeCase(field), value, expected_updated_at: expectedUpdatedAt,
  }).then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationCustomTextField = (id, definition, value, expectedUpdatedAt) => (
  api.patch(`/projects/annotation/${id}/custom-fields/${definition.id}/text`, {
    field: definition.fieldKey, value, expected_updated_at: expectedUpdatedAt,
  }).then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationProjectStatus = (id, payload) => (
  api.patch(`/projects/annotation/${id}/status`, convertKeys(payload, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationProjectPriority = (id, priority) => (
  api.patch(`/projects/annotation/${id}/priority`, { priority }).then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationProjectManagers = (id, data) => (
  api.patch(`/projects/annotation/${id}/managers`, convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const getAnnotationManagerChangeLogs = (params = {}, config = {}) => (
  api.get('/projects/annotation/manager-change-logs', { ...config, params })
    .then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationProjectOrderNo = (id, data) => (
  api.patch(`/projects/annotation/${id}/order-no`, convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const deleteAnnotationProject = (id) => api.delete(`/projects/annotation/${id}`).then((res) => {
  invalidateOptionCache('source-projects:annotation:')
  return res
})

export const previewAnnotationProjectName = (data) => (
  api.post('/projects/annotation/name-preview', convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)
