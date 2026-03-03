import api from './index'

export const getOnLeaveUsers = (date) => api.get('/leave/on-leave', { params: { date } })
export const getLeaveRecords = (params) => api.get('/leave/', { params })
export const createLeave = (data) => api.post('/leave/', data)
export const updateLeave = (id, data) => api.put(`/leave/${id}`, data)
export const deleteLeave = (id) => api.delete(`/leave/${id}`)
