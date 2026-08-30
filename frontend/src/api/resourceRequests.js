import api from './index'
import { clearIdempotencyKey, resetIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'

const requestCreateState = { key: '', signature: '' }
export const resetResourceRequestIdempotency = () => resetIdempotencyKey(requestCreateState)

const snake = (value) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
const camel = (value) => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const convert = (value, keyFn) => Array.isArray(value) ? value.map((item) => convert(item, keyFn)) : value && value.constructor === Object ? Object.fromEntries(Object.entries(value).map(([key, item]) => [keyFn(key), convert(item, keyFn)])) : value

export const getResourceRequests = (params, config = {}) => api.get('/resource-requests/', { ...config, params }).then((res) => convert(res, camel))
export const getResourceRequestCount = (params, config = {}) => api.get('/resource-requests/count', { ...config, params })
export const getResourceRequestSourcePrefill = (sourceType, sourceProjectId) => api.get('/resource-requests/source-prefill', { params: { source_type: sourceType, source_project_id: sourceProjectId } }).then((res) => convert(res, camel))
export const getResourceRequest = (id) => api.get(`/resource-requests/${id}`).then((res) => convert(res, camel))
export const createResourceRequest = async (data, idempotencyKey) => {
  const payload = convert(data, snake)
  const key = resolveIdempotencyKey(requestCreateState, payload, idempotencyKey)
  const response = await api.post('/resource-requests/', payload, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(requestCreateState, key)
  return convert(response, camel)
}
export const updateResourceRequest = (id, data) => api.put(`/resource-requests/${id}`, convert(data, snake)).then((res) => convert(res, camel))
export const updateResourceRequestTextField = (id, field, value, expectedUpdatedAt) => api.patch(`/resource-requests/${id}/text-field`, {
  field: snake(field), value, expected_updated_at: expectedUpdatedAt,
}).then((res) => convert(res, camel))
export const updateResourceRequestItemTextField = (id, itemId, field, value, expectedUpdatedAt) => api.patch(`/resource-requests/${id}/items/${itemId}/text-field`, {
  field: snake(field), value, expected_updated_at: expectedUpdatedAt,
}).then((res) => convert(res, camel))
export const updateResourceProgress = (id, data) => api.patch(`/resource-requests/${id}/progress`, convert(data, snake)).then((res) => convert(res, camel))
export const getResourceProgressLogs = (id) => api.get(`/resource-requests/${id}/progress-logs`).then((res) => convert(res, camel))
export const deleteResourceRequest = (id) => api.delete(`/resource-requests/${id}`)
