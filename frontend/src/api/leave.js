import api from './index'

export const getOnLeaveUsers = (date) => api.get('/leave/on-leave', { params: { date } })
export const getLeaveRecords = () => api.get('/leave/')
export const createLeave = (data) => api.post('/leave/', data)
export const deleteLeave = (id) => api.delete(`/leave/${id}`)
