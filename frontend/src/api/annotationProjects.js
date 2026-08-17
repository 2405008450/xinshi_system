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

export const getAnnotationProjects = (params, config = {}) => (
  api.get('/projects/annotation/', { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const getAnnotationProjectCount = (params, config = {}) => (
  api.get('/projects/annotation/count', { ...config, params })
)

export const getAnnotationProject = (id) => (
  api.get(`/projects/annotation/${id}`).then((res) => convertKeys(res, toCamelCase))
)

export const createAnnotationProject = (data) => (
  api.post('/projects/annotation/', convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationProject = (id, data) => (
  api.put(`/projects/annotation/${id}`, convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const updateAnnotationProjectStatus = (id, projectStatus) => (
  api.patch(`/projects/annotation/${id}/status`, { project_status: projectStatus }).then((res) => convertKeys(res, toCamelCase))
)

export const deleteAnnotationProject = (id) => api.delete(`/projects/annotation/${id}`)

export const previewAnnotationProjectName = (data) => (
  api.post('/projects/annotation/name-preview', convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)
