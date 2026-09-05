import api from './index'

export const getUsers = (params, signal) => api.get('/users/', { params, signal })
export const getUserCount = (params, signal) => api.get('/users/count', { params, signal })
export const getUserPage = (params, signal) => api.get('/users/page', { params, signal })
export const getUserOptions = (params = {}, signal) => api.get('/users/options', { params, signal })
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
export const getUserMailAccount = (id) => api.get(`/users/${id}/mail-account`)
export const saveUserMailAccount = (id, authorizationCode) =>
  api.put(`/users/${id}/mail-account`, { authorization_code: authorizationCode })
export const verifyUserMailAccount = (id) => api.post(`/users/${id}/mail-account/verify`)
export const deleteUserMailAccount = (id) => api.delete(`/users/${id}/mail-account`)
export const getUserMailProfile = (id) => api.get(`/users/${id}/mail-profile`)
export const saveUserMailProfile = (id, data) => api.put(`/users/${id}/mail-profile`, data)
export const deleteUser = (id) => api.delete(`/users/${id}`)
