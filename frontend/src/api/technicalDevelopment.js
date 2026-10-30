import api from './index'

const root = '/technical-development'
export const getDevelopmentPeople = () => api.get(`${root}/people`)
export const getDevelopmentTasks = (signal) => api.get(`${root}/tasks`, { signal })
export const getDevelopmentTask = (id) => api.get(`${root}/tasks/${id}`)
export const createDevelopmentTask = (data) => api.post(`${root}/tasks`, data, { timeout: data.allocations ? 60000 : 10000 })
export const updateDevelopmentTask = (id, data) => api.put(`${root}/tasks/${id}`, data, { timeout: data.allocations ? 60000 : 10000 })
export const moveDevelopmentTask = (id, data) => api.put(`${root}/tasks/${id}/parent`, data)
export const deleteDevelopmentTask = (id, revision) => api.delete(`${root}/tasks/${id}`, { params: { revision } })
export const swapDevelopmentTasks = (id, data) => api.put(`${root}/tasks/${id}/swap`, data)
export const saveDevelopmentProgress = (id, data) => api.post(`${root}/tasks/${id}/progress`, data)
export const addDevelopmentFeedback = (id, data) => api.post(`${root}/tasks/${id}/feedback`, data)
export const getDevelopmentReportContext = (id) => api.get(`${root}/tasks/${id}/report`)
export const addDevelopmentReport = (id, data) => api.post(`${root}/tasks/${id}/report`, data)
