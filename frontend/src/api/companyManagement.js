import api from './index'

const toCamelCase = value => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const convertKeys = value => {
  if (Array.isArray(value)) return value.map(convertKeys)
  if (value && value.constructor === Object) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [toCamelCase(key), convertKeys(item)]))
  }
  return value
}

export const getCompanyManagementNoticeTree = () => (
  api.get('/company-management/tree').then(convertKeys)
)

export const getCompanyManagementNoticeDetail = sectionId => (
  api.get(`/company-management/sections/${sectionId}`).then(convertKeys)
)

export const createCompanyManagementNotice = payload => (
  api.post('/company-management/sections', {
    title: payload.title,
    parent_id: payload.parentId || null,
    has_content: payload.hasContent
  }).then(convertKeys)
)

export const updateCompanyManagementNoticeStructure = (sectionId, payload) => (
  api.patch(`/company-management/sections/${sectionId}`, {
    title: payload.title,
    has_content: payload.hasContent,
    expected_structure_updated_at: payload.expectedStructureUpdatedAt || null
  }).then(convertKeys)
)

export const deleteCompanyManagementNotice = sectionId => api.delete(`/company-management/sections/${sectionId}`)

export const reorderCompanyManagementNotices = placements => (
  api.put('/company-management/sections/reorder', {
    placements: placements.map(item => ({
      id: item.id,
      parent_id: item.parentId || null,
      sort_order: item.sortOrder,
      expected_structure_updated_at: item.expectedStructureUpdatedAt || null
    }))
  }).then(convertKeys)
)

export const searchCompanyManagementNotices = (params, config = {}) => (
  api.get('/company-management/search', { params: {
    keyword: params.keyword,
    skip: params.skip || 0,
    limit: params.limit || 20
  }, ...config }).then(convertKeys)
)

export const updateCompanyManagementNoticeContent = (sectionId, contentJson, expectedUpdatedAt) => (
  api.put(`/company-management/sections/${sectionId}/content`, {
    content_json: contentJson,
    expected_updated_at: expectedUpdatedAt || null
  }).then(convertKeys)
)

export const adapter = {
  images: {
    upload: uploadContentImage,
    read: readContentImage,
    removeDraft: removeContentImageDraft
  },
  tree: getCompanyManagementNoticeTree,
  detail: getCompanyManagementNoticeDetail,
  search: searchCompanyManagementNotices,
  saveContent: updateCompanyManagementNoticeContent,
  create: createCompanyManagementNotice,
  updateStructure: updateCompanyManagementNoticeStructure,
  remove: deleteCompanyManagementNotice,
  reorder: reorderCompanyManagementNotices
}

export const listAttachments = (sectionId, signal) => api.get(
  `/company-management/sections/${sectionId}/attachments`, { signal }
).then(convertKeys)

export function uploadAttachment(sectionId, file, onUploadProgress, signal) {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/company-management/sections/${sectionId}/attachments`, form, {
    headers: { 'Content-Type': undefined },
    timeout: 120000, onUploadProgress, signal
  }).then(convertKeys)
}

export const downloadAttachment = (sectionId, attachmentId) => api.get(
  `/company-management/sections/${sectionId}/attachments/${attachmentId}`,
  { responseType: 'blob', timeout: 120000 }
)

export const deleteAttachment = (sectionId, attachmentId) => api.delete(
  `/company-management/sections/${sectionId}/attachments/${attachmentId}`
)

export function uploadContentImage(sectionId, file, signal) {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/company-management/sections/${sectionId}/images`, form, {
    headers: { 'Content-Type': undefined }, timeout: 120000, signal
  }).then(convertKeys)
}

export function readContentImage(src, signal) {
  // 只接收本模块的受控地址，避免将登录凭据发送到粘贴来源。
  if (!/^\/api\/company-management\/sections\/[0-9a-f-]{36}\/images\/[0-9a-f-]{36}$/.test(src)) {
    return Promise.reject(new Error('正文图片地址无效'))
  }
  return api.get(src.slice(4), { responseType: 'blob', timeout: 120000, signal })
}

export function removeContentImageDraft(sectionId, imageId) {
  return api.delete(`/company-management/sections/${sectionId}/images/${imageId}`)
}
