import api from './index'

export const getThoughtAiState = (config = {}) => api.get('/thoughts-ai/latest', config)
export const createThoughtAiJob = (data, config = {}) => api.post('/thoughts-ai/jobs', data, config)
export const cancelThoughtAiJob = (id, config = {}) => api.post(`/thoughts-ai/jobs/${id}/cancel`, undefined, config)
