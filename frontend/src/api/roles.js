import api from './index'

export const getRoles = (params) => api.get('/roles/', { params })
export const getRole = (id) => api.get(`/roles/${id}`)
export const createRole = (data) => api.post('/roles/', data)
export const updateRole = (id, data) => api.put(`/roles/${id}`, data)
export const deleteRole = (id) => api.delete(`/roles/${id}`)
export const updateRolePermissions = (id, permissions) =>
  api.put(`/roles/${id}/permissions`, { permissions })
export const getPermissionCatalog = () => api.get('/permissions/catalog')
