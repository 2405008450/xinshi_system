import api from './index'
import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'

const talentCreateState = { key: '', signature: '' }

const convertKeys = (value, converter) => {
  if (Array.isArray(value)) return value.map((item) => convertKeys(item, converter))
  if (value && value.constructor === Object) return Object.fromEntries(Object.entries(value).map(([key, item]) => [converter(key), convertKeys(item, converter)]))
  return value
}
const toCamelCase = (value) => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const toSnakeCase = (value) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
const fromApi = (value) => convertKeys(value, toCamelCase)
const toApi = (value) => convertKeys(value, toSnakeCase)

export const getTalents = (params, config = {}) => api.get('/talents/', { ...config, params }).then(fromApi)
export const getTalentCount = (params, config = {}) => api.get('/talents/count', { ...config, params })
export const getTalent = (id) => api.get(`/talents/${id}`).then(fromApi)
export const createTalent = async (data) => {
  const payload = toApi(data)
  const key = resolveIdempotencyKey(talentCreateState, payload)
  const response = await api.post('/talents/', payload, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(talentCreateState, key)
  return fromApi(response)
}
export const updateTalent = (id, data) => api.put(`/talents/${id}`, toApi(data)).then(fromApi)
export const patchTalentName = (id, fullName) => api.patch(`/talents/${id}/name`, toApi({ fullName })).then(fromApi)
export const patchTalentStatus = (id, status) => api.patch(`/talents/${id}/status`, toApi({ status })).then(fromApi)
export const deleteTalent = (id) => api.delete(`/talents/${id}`)
export const checkTalentDuplicates = (params) => api.get('/talents/duplicates', { params }).then(fromApi)

export const getRecruitmentTalents = (params, config = {}) => api.get('/recruitment-talents/', { ...config, params }).then(fromApi)
export const getRecruitmentTalentCount = (params, config = {}) => api.get('/recruitment-talents/count', { ...config, params })
export const getRecruitmentTalent = (id) => api.get(`/recruitment-talents/${id}`).then(fromApi)
export const createRecruitmentTalent = (data) => api.post('/recruitment-talents/', toApi(data)).then(fromApi)
export const updateRecruitmentTalent = (id, data) => api.put(`/recruitment-talents/${id}`, toApi(data)).then(fromApi)
export const patchRecruitmentTalentStatus = (id, status) => api.patch(`/recruitment-talents/${id}/status`, toApi({ status })).then(fromApi)
export const deleteRecruitmentTalent = (id) => api.delete(`/recruitment-talents/${id}`)
export const checkRecruitmentTalentDuplicates = (params) => api.get('/recruitment-talents/duplicates', { params }).then(fromApi)

export const getProjectTalentOptions = (capabilityType, params = {}, config = {}) => api.get('/talent-options/', {
  ...config,
  params: { ...params, capability_type: capabilityType }
}).then(fromApi)
