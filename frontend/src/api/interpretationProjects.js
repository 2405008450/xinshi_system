import api from './index'

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

export const getInterpretationProject = (id) => (
  api.get(`/projects/interpretation/${id}`).then((res) => convertKeys(res, toCamelCase))
)

export const createInterpretationProject = (data) => (
  api.post('/projects/interpretation/', convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const updateInterpretationProject = (id, data) => (
  api.put(`/projects/interpretation/${id}`, convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const updateInterpretationProjectStatus = (id, projectStatus) => (
  api.patch(`/projects/interpretation/${id}/status`, { project_status: projectStatus })
    .then((res) => convertKeys(res, toCamelCase))
)

export const deleteInterpretationProject = (id) => api.delete(`/projects/interpretation/${id}`)

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
