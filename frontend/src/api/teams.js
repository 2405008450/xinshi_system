import api from './index'
const attachmentMetadata = row => Object.fromEntries(Object.entries(row).map(([key, value]) => [key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()), value]))

export const teamApi = {
  options: signal => api.get('/teams/options', { signal }),
  list: (params, signal) => api.get('/teams', { params, signal, paramsSerializer: { indexes: null } }),
  detail: (id, signal) => api.get(`/teams/${id}`, { signal }),
  save: (data, id) => id ? api.put(`/teams/${id}`, data) : api.post('/teams', data),
  delete: row => api.delete(`/teams/${row.id}`, { params: { revision: row.revision } }),
}

export const teamAttachmentAdapter = {
  list: (id, signal) => api.get(`/teams/${id}/attachments`, { signal }).then(rows => rows.map(attachmentMetadata)),
  upload: (id, file, onUploadProgress, signal) => {
    const form = new FormData(); form.append('file', file)
    return api.post(`/teams/${id}/attachments`, form, { headers: { 'Content-Type': undefined }, timeout: 120000, onUploadProgress, signal }).then(attachmentMetadata)
  },
  download: (id, attachmentId, signal) => api.get(`/teams/${id}/attachments/${attachmentId}`, { responseType: 'blob', timeout: 120000, signal }),
  remove: (id, attachmentId, signal) => api.delete(`/teams/${id}/attachments/${attachmentId}`, { signal })
}
