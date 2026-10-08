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
export const getTalentPage = (params, config = {}) => api.get('/talents/page', { ...config, params }).then(fromApi)
export const getTalentOverview = () => api.get('/talents/overview').then(fromApi)
const overviewLanguagePath = key => `/talents/overview/languages/${encodeURIComponent(key)}`
const overviewGroupPath = id => `/talents/overview/groups/${id}`
export const getOverviewLanguageManagement = key => api.get(`${overviewLanguagePath(key)}/management`).then(fromApi)
export const saveOverviewLanguageManagement = (key, data) => api.put(`${overviewLanguagePath(key)}/management`, toApi(data)).then(fromApi)
export const getOverviewGroups = (key, includeArchived = false) => api.get(`${overviewLanguagePath(key)}/groups`, { params: { include_archived: includeArchived } }).then(fromApi)
export const createOverviewGroup = (key, data) => api.post(`${overviewLanguagePath(key)}/groups`, toApi(data)).then(fromApi)
export const getOverviewGroup = id => api.get(overviewGroupPath(id)).then(fromApi)
export const updateOverviewGroup = (id, data) => api.put(overviewGroupPath(id), toApi(data)).then(fromApi)
export const archiveOverviewGroup = (id, data) => api.put(`${overviewGroupPath(id)}/archive`, toApi(data)).then(fromApi)
export const registerOverviewGroupCount = (id, data) => api.post(`${overviewGroupPath(id)}/counts`, toApi(data)).then(fromApi)
export const voidOverviewGroupCount = (id, countId, data) => api.put(`${overviewGroupPath(id)}/counts/${countId}/void`, toApi(data)).then(fromApi)
export const getOverviewGroupCounts = (id, page = 1) => api.get(`${overviewGroupPath(id)}/counts`, { params: { page } }).then(fromApi)
export const getOverviewGroupHistory = (id, page = 1) => api.get(`${overviewGroupPath(id)}/history`, { params: { page } }).then(fromApi)
export const getOverviewLanguageHistory = (key, page = 1) => api.get(`${overviewLanguagePath(key)}/history`, { params: { page } }).then(fromApi)
export const getTalentPoolStatistics = () => api.get('/talents/overview/pool-statistics').then(fromApi)
export const saveTalentOverview = (data) => api.put('/talents/overview', {
  expected_revision: data.expectedRevision,
  columns: data.columns.map(column => ({
    key: column.key,
    label: column.label,
    group: column.group,
    width: column.width,
  })),
  rows: data.rows.map(row => ({
    overview_key: row.overviewKey,
    language: row.language,
    language_id: row.languageId || null,
    updated_at: row.updatedAt || null,
    // counts 的键是服务端认可的动态列标识，不参与 snake_case 转换。
    counts: Object.fromEntries(Object.entries(row.counts || {})),
  })),
}).then(fromApi)
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
export const getTalentProjects = (id) => api.get(`/talents/${id}/projects`).then(fromApi)
export const getTalentProjectPage = (id, params = {}, config = {}) => api.get(
  `/talents/${id}/projects/page`, { ...config, params: toApi(params) },
).then(fromApi)
export const getTalentAnnotationProjectPerformance = (personId, projectId, config = {}) => api.get(
  `/talents/${personId}/projects/annotation/${projectId}/performance`, config,
).then(fromApi)
export const uploadTalentAttachment = (id, category, file, certificateId = null) => {
  const form = new FormData()
  form.append('category', category)
  if (certificateId) form.append('certificate_id', certificateId)
  form.append('file', file)
  return api.post(`/talents/${id}/attachments`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(fromApi)
}
export const getTalentAttachmentBlob = (id, attachmentId) => api.get(
  `/talents/${id}/attachments/${attachmentId}`,
  { responseType: 'blob' },
)
export const deleteTalentAttachment = (id, attachmentId) => api.delete(`/talents/${id}/attachments/${attachmentId}`)

export const getRecruitmentTalents = (params, config = {}) => api.get('/recruitment-talents/', { ...config, params }).then(fromApi)
export const getRecruitmentTalentCount = (params, config = {}) => api.get('/recruitment-talents/count', { ...config, params })
export const getRecruitmentTalent = (id) => api.get(`/recruitment-talents/${id}`).then(fromApi)
export const getRecruitmentTalentProjects = (id) => api.get(`/recruitment-talents/${id}/projects`).then(fromApi)
export const createRecruitmentTalent = (data) => api.post('/recruitment-talents/', toApi(data)).then(fromApi)
export const updateRecruitmentTalent = (id, data) => api.put(`/recruitment-talents/${id}`, toApi(data)).then(fromApi)
export const patchRecruitmentTalentStatus = (id, status) => api.patch(`/recruitment-talents/${id}/status`, toApi({ status })).then(fromApi)
export const deleteRecruitmentTalent = (id) => api.delete(`/recruitment-talents/${id}`)
export const checkRecruitmentTalentDuplicates = (params) => api.get('/recruitment-talents/duplicates', { params }).then(fromApi)

export const getProjectTalentOptions = (capabilityType, params = {}, config = {}) => api.get('/talent-options/', {
  ...config,
  params: { ...params, capability_type: capabilityType }
}).then(fromApi)
