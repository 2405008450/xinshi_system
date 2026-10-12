import api from './index'

export const teamApi = {
  options: signal => api.get('/teams/options', { signal }),
  list: (params, signal) => api.get('/teams', { params, signal, paramsSerializer: { indexes: null } }),
  detail: (id, signal) => api.get(`/teams/${id}`, { signal }),
  save: (data, id) => id ? api.put(`/teams/${id}`, data) : api.post('/teams', data),
  delete: row => api.delete(`/teams/${row.id}`, { params: { revision: row.revision } }),
}
