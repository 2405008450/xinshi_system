import api from './index'

const convertKeys = value => {
  if (Array.isArray(value)) return value.map(convertKeys)
  if (value && value.constructor === Object) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
      key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()), convertKeys(item)
    ]))
  }
  return value
}

// 每个实例固定板块，避免切换页面后请求或附件进入其他业务库。
export function createProjectNoticeAdapter(module) {
  const base = `/project-notices/${module}`
  const section = id => `${base}/sections/${id}`
  return {
    tree: () => api.get(`${base}/tree`).then(convertKeys),
    detail: id => api.get(section(id)).then(convertKeys),
    search: (params, config = {}) => api.get(`${base}/search`, { params, ...config }).then(convertKeys),
    create: payload => api.post(`${base}/sections`, {
      title: payload.title, parent_id: payload.parentId || null, has_content: payload.hasContent
    }).then(convertKeys),
    updateStructure: (id, payload) => api.patch(section(id), {
      title: payload.title, has_content: payload.hasContent,
      expected_structure_updated_at: payload.expectedStructureUpdatedAt || null
    }).then(convertKeys),
    remove: id => api.delete(section(id)),
    reorder: placements => api.put(`${base}/sections/reorder`, {
      placements: placements.map(item => ({
        id: item.id, parent_id: item.parentId || null, sort_order: item.sortOrder,
        expected_structure_updated_at: item.expectedStructureUpdatedAt || null
      }))
    }).then(convertKeys),
    saveContent: (id, content, version) => api.put(`${section(id)}/content`, {
      content_json: content, expected_updated_at: version || null
    }).then(convertKeys),
    attachments: {
      list: (id, signal) => api.get(`${section(id)}/attachments`, { signal }).then(convertKeys),
      upload: (id, file, onUploadProgress, signal) => {
        const form = new FormData()
        form.append('file', file)
        return api.post(`${section(id)}/attachments`, form, {
          headers: { 'Content-Type': undefined }, timeout: 120000, onUploadProgress, signal
        }).then(convertKeys)
      },
      download: (id, attachmentId, signal) => api.get(`${section(id)}/attachments/${attachmentId}`, {
        responseType: 'blob', timeout: 120000, signal
      }),
      remove: (id, attachmentId, signal) => api.delete(`${section(id)}/attachments/${attachmentId}`, { signal })
    }
  }
}
