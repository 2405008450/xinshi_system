import api from './index'
const base = '/resource-development'
export const developmentApi = {
  options: () => api.get(`${base}/options`),
  saveOption: (data, id) => id ? api.put(`${base}/options/${id}`, data) : api.post(`${base}/options`, data),
  addLanguage: data => api.post(`${base}/languages`, data),
  days: (params, signal) => api.get(`${base}/days`, { params, signal }),
  records: (params, signal) => api.get(`${base}/records`, { params, signal }),
  detail: id => api.get(`${base}/records/${id}`),
  save: data => api.post(`${base}/records`, data),
  duplicates: data => api.post(`${base}/duplicates`, data),
  remove: row => api.delete(`${base}/records/${row.id}`, { params: { revision: row.revision } }),
  work: params => api.get(`${base}/work`, { params }),
  saveWork: data => api.put(`${base}/work`, data),
  upload: (id, file) => {
    const form = new FormData(); form.append('file', file)
    return api.post(`${base}/work/${id}/screenshots`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  screenshot: id => api.get(`${base}/screenshots/${id}`, { responseType: 'blob' }),
  removeScreenshot: id => api.delete(`${base}/screenshots/${id}`),
}
