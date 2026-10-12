import api from './index'

export const listNoticeAttachments = (sectionId, signal) => api.get(
  `/annotation-notices/sections/${sectionId}/attachments`, { signal }
).then(convertKeys)

export function uploadNoticeAttachment(sectionId, file, onUploadProgress, signal) {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/annotation-notices/sections/${sectionId}/attachments`, form, {
    headers: { 'Content-Type': undefined }, timeout: 120000, onUploadProgress, signal
  }).then(convertKeys)
}

export const downloadNoticeAttachment = (sectionId, attachmentId, signal) => api.get(
  `/annotation-notices/sections/${sectionId}/attachments/${attachmentId}`,
  { responseType: 'blob', timeout: 120000, signal }
)

export const deleteNoticeAttachment = (sectionId, attachmentId, signal) => api.delete(
  `/annotation-notices/sections/${sectionId}/attachments/${attachmentId}`, { signal }
)

export const attachmentAdapter = {
  list: listNoticeAttachments, upload: uploadNoticeAttachment,
  download: downloadNoticeAttachment, remove: deleteNoticeAttachment
}

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

export const getAnnotationNoticeTree = () => (
  api.get('/annotation-notices/tree').then(convertKeys)
)

export const getAnnotationNoticeDetail = sectionId => (
  api.get(`/annotation-notices/sections/${sectionId}`).then(convertKeys)
)

export const createAnnotationNotice = payload => (
  api.post('/annotation-notices/sections', {
    title: payload.title,
    parent_id: payload.parentId || null,
    has_content: payload.hasContent
  }).then(convertKeys)
)

export const updateAnnotationNoticeStructure = (sectionId, payload) => (
  api.patch(`/annotation-notices/sections/${sectionId}`, {
    title: payload.title,
    has_content: payload.hasContent,
    expected_structure_updated_at: payload.expectedStructureUpdatedAt || null
  }).then(convertKeys)
)

export const deleteAnnotationNotice = sectionId => api.delete(`/annotation-notices/sections/${sectionId}`)

export const reorderAnnotationNotices = placements => (
  api.put('/annotation-notices/sections/reorder', {
    placements: placements.map(item => ({
      id: item.id,
      parent_id: item.parentId || null,
      sort_order: item.sortOrder,
      expected_structure_updated_at: item.expectedStructureUpdatedAt || null
    }))
  }).then(convertKeys)
)

export const searchAnnotationNotices = (params, config = {}) => (
  api.get('/annotation-notices/search', { params: {
    keyword: params.keyword,
    skip: params.skip || 0,
    limit: params.limit || 20
  }, ...config }).then(convertKeys)
)

export const updateAnnotationNoticeContent = (sectionId, contentJson, expectedUpdatedAt) => (
  api.put(`/annotation-notices/sections/${sectionId}/content`, {
    content_json: contentJson,
    expected_updated_at: expectedUpdatedAt || null
  }).then(convertKeys)
)

export const updateAnnotationNotice = (sectionKey, contentJson, expectedUpdatedAt) => (
  api.put(`/annotation-notices/${sectionKey}`, {
    content_json: contentJson,
    expected_updated_at: expectedUpdatedAt || null
  }).then(convertKeys)
)
