import api from './index'

export const getOnLeaveUsers = (date, signal) => api.get('/leave/on-leave', { params: { date }, signal })
export const getLeaveRecords = (params, signal) => api.get('/leave/', { params, signal })
export const getLeaveOverview = (params) => api.get('/leave/overview', { params })
export const createLeave = (data) => api.post('/leave/', data)
export const updateLeave = (id, data) => api.put(`/leave/${id}`, data)
export const deleteLeave = (id) => api.delete(`/leave/${id}`)
