import api from './index'
export const getDevelopmentFeedback = signal => api.get('/development-feedback', { signal })
export const generateFeedbackSheet = id => api.post(`/development-feedback/tasks/${id}/generate`)
export const createFeedbackRow = (id, requestId) => api.post(`/development-feedback/tasks/${id}/rows`, { request_id: requestId })
export const updateFeedbackRow = (id, data) => api.patch(`/development-feedback/rows/${id}`, data)
export const addFeedbackOpinion = (id, data) => api.post(`/development-feedback/rows/${id}/opinions`, data)
