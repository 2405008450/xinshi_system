import api from './index'

export const getUserRoles = (params) => api.get('/user-roles/', { params })
export const getUserRolesByUser = (userId) => api.get(`/user-roles/user/${userId}`)
export const getUserRolesByRole = (roleId) => api.get(`/user-roles/role/${roleId}`)
export const getUserRole = (id) => api.get(`/user-roles/${id}`)
export const createUserRole = (data) => api.post('/user-roles/', data)
export const deleteUserRole = (id) => api.delete(`/user-roles/${id}`)
export const deleteUserRoleByUserAndRole = (userId, roleId) => 
  api.delete(`/user-roles/user/${userId}/role/${roleId}`)
