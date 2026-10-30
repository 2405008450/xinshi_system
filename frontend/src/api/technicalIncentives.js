import api from './index'
export const getTaskCompletion = id => api.get(`/technical-development/tasks/${id}/completion`)
export const saveTaskCompletion = (id, data) => api.put(`/technical-development/tasks/${id}/completion`, data)
export const saveTaskIncentive = (id, data) => api.post(`/technical-development/tasks/${id}/incentive`, data)
export const getTechnicalIncentives = signal => api.get('/technical-development/incentives', { signal })
