import api from './index'

const toCamelCase = (value) => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const toSnakeCase = (value) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
const convertKeys = (value, converter) => {
  if (Array.isArray(value)) return value.map((item) => convertKeys(item, converter))
  if (value && value.constructor === Object) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [converter(key), convertKeys(item, converter)]))
  }
  return value
}

export const getComparisonGroupPage = (params, config = {}) => (
  api.get('/projects/annotation-comparisons/page', { ...config, params }).then((res) => convertKeys(res, toCamelCase))
)

export const getComparisonGroup = (id, config = {}) => (
  api.get(`/projects/annotation-comparisons/${id}`, config).then((res) => convertKeys(res, toCamelCase))
)

export const createComparisonGroup = (data) => (
  api.post('/projects/annotation-comparisons', convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const updateComparisonGroup = (id, data) => (
  api.patch(`/projects/annotation-comparisons/${id}`, convertKeys(data, toSnakeCase)).then((res) => convertKeys(res, toCamelCase))
)

export const deleteComparisonGroup = (id) => api.delete(`/projects/annotation-comparisons/${id}`)
