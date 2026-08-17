import api from './index'

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
export const createTalent = (data) => api.post('/talents/', toApi(data)).then(fromApi)
export const updateTalent = (id, data) => api.put(`/talents/${id}`, toApi(data)).then(fromApi)
export const checkTalentDuplicates = (params) => api.get('/talents/duplicates', { params }).then(fromApi)

export const getRecruitmentTalents = (params, config = {}) => api.get('/recruitment-talents/', { ...config, params }).then(fromApi)
export const getRecruitmentTalentCount = (params, config = {}) => api.get('/recruitment-talents/count', { ...config, params })
export const getRecruitmentTalent = (id) => api.get(`/recruitment-talents/${id}`).then(fromApi)
export const createRecruitmentTalent = (data) => api.post('/recruitment-talents/', toApi(data)).then(fromApi)
export const updateRecruitmentTalent = (id, data) => api.put(`/recruitment-talents/${id}`, toApi(data)).then(fromApi)
export const checkRecruitmentTalentDuplicates = (params) => api.get('/recruitment-talents/duplicates', { params }).then(fromApi)

export const getProjectTalentOptions = (capabilityType, params = {}, config = {}) => api.get('/talent-options/', {
  ...config,
  params: { ...params, capability_type: capabilityType }
}).then(fromApi)
