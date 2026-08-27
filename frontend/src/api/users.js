import api from './index'

export const getUsers = (params, signal) => api.get('/users/', { params, signal })
export const getUserCount = (params, signal) => api.get('/users/count', { params, signal })
export const checkEmailAvailability = (email, excludeUserId) => api.get('/users/email-availability', {
  params: {
    email,
    exclude_user_id: excludeUserId || undefined
  }
})
export const getUser = (id) => api.get(`/users/${id}`)
export const createUser = (data) => api.post('/users/', data)
export const updateUser = (id, data) => api.put(`/users/${id}`, data)
export const resetUserPassword = (id, newPassword) =>
  api.put(`/users/${id}/password`, { new_password: newPassword })
export const deleteUser = (id) => api.delete(`/users/${id}`)
