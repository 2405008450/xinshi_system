import api from './index'
const base = '/chat/topics'
export const topicApi = {
  tree: () => api.get(base),
  create: data => api.post(base, data),
  update: (id, data) => api.put(`${base}/${id}`, data),
  classify: (id, data) => api.put(`${base}/messages/${id}`, data),
  message: id => api.get(`${base}/messages/${id}`),
  search: (params, signal) => api.get(`${base}/search`, { params, signal }),
}
