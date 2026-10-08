import api from './index'

const base = '/referral-development'
export const referralApi = {
  options: () => api.get(`${base}/options`),
  records: (params, signal) => api.get(`${base}/records`, { params, signal }),
  detail: (id, signal) => api.get(`${base}/records/${id}`, { signal }),
  duplicates: (params, signal) => api.get(`${base}/duplicates`, { params, signal }),
  save: data => api.post(`${base}/records`, data),
  payment: (id, data) => api.put(`${base}/records/${id}/payment`, data),
  remove: row => api.delete(`${base}/records/${row.id}`, { params: { revision: row.revision } }),
  upload: (record, item) => {
    const form = new FormData()
    form.append('file', item.file)
    form.append('category', item.category)
    form.append('image_id', item.id)
    form.append('revision', String(record.revision))
    return api.post(`${base}/records/${record.id}/images`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  image: (id, signal) => api.get(`${base}/images/${id}`, { responseType: 'blob', signal }),
  removeImage: (record, id) => api.delete(`${base}/records/${record.id}/images/${id}`, { params: { revision: record.revision } }),
}
