import api from './index'
const base = '/resource-development'
export const developmentApi = {
  options: () => api.get(`${base}/options`),
  channels: (params, signal) => api.get(`${base}/channels`, { params, signal, paramsSerializer: { indexes: null } }),
  channelPeople: () => api.get(`${base}/channels/people`),
  channel: (id, signal) => api.get(`${base}/channels/${id}`, { signal }),
  saveChannel: (data, id) => id ? api.put(`${base}/channels/${id}`, data) : api.post(`${base}/channels`, data),
  saveChannelDescription: (id, data) => api.put(`${base}/channels/${id}/description`, data),
  saveOption: (data, id) => id ? api.put(`${base}/options/${id}`, data) : api.post(`${base}/options`, data),
  addLanguage: data => api.post(`${base}/languages`, data),
  days: (params, signal) => api.get(`${base}/days`, { params, signal }),
  records: (params, signal) => api.get(`${base}/records`, { params, signal }),
  detail: (id, signal) => api.get(`${base}/records/${id}`, { signal }),
  save: data => api.post(`${base}/records`, data),
  saveGroupAction: (id, data) => api.post(`${base}/records/${id}/group-actions`, data),
  duplicates: data => api.post(`${base}/duplicates`, data),
  recordDuplicates: (params, signal) => api.get(`${base}/record-duplicates`, { params, signal }),
  remove: row => api.delete(`${base}/records/${row.id}`, { params: { revision: row.revision } }),
  work: params => api.get(`${base}/work`, { params }),
  saveWork: data => api.put(`${base}/work`, data),
  upload: (id, file) => {
    const form = new FormData(); form.append('file', file)
    return api.post(`${base}/work/${id}/screenshots`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  screenshot: id => api.get(`${base}/screenshots/${id}`, { responseType: 'blob' }),
  removeScreenshot: id => api.delete(`${base}/screenshots/${id}`),
  arrangements: (params, signal) => api.get(`${base}/arrangements`, { params, signal }),
  arrangement: (day, signal) => api.get(`${base}/arrangements/${day}`, { signal }),
  carryArrangement: day => api.get(`${base}/arrangements/${day}/carry-preview`),
  saveArrangement: (day, data) => api.put(`${base}/arrangements/${day}`, data),
  completeArrangement: (day, platform, data) => api.patch(`${base}/arrangements/${day}/cells/${platform}/completion`, data),
  arrangementOptions: (params, signal) => api.get(`${base}/arrangement-options`, { params, signal }),
  arrangementProject: (params, signal) => api.get(`${base}/arrangement-project-detail`, { params, signal }),
}
