import api from './index'

export const getUsers = (params) => api.get('/users/', { params })
export const getUserCount = (params) => api.get('/users/count', { params })
export const getUser = (id) => api.get(`/users/${id}`)
export const createUser = (data) => api.post('/users/', data)
export const updateUser = (id, data) => api.put(`/users/${id}`, data)
export const resetUserPassword = (id, newPassword) =>
  api.put(`/users/${id}/password`, { new_password: newPassword })
export const deleteUser = (id) => api.delete(`/users/${id}`)
