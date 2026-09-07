import api from './index'

const toCamelCase = value => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const convertKeys = value => {
  if (Array.isArray(value)) return value.map(convertKeys)
  if (value && value.constructor === Object) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [toCamelCase(key), convertKeys(item)]))
  }
  return value
}

export const getAnnotationNotices = () => (
  api.get('/annotation-notices').then(convertKeys)
)

export const updateAnnotationNotice = (sectionKey, contentJson, expectedUpdatedAt) => (
  api.put(`/annotation-notices/${sectionKey}`, {
    content_json: contentJson,
    expected_updated_at: expectedUpdatedAt || null
  }).then(convertKeys)
)
