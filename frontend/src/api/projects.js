import api from './index'

export const getProjects = (params) => api.get('/projects/translation/', { params })
export const getProject = (id) => api.get(`/projects/translation/${id}`)
export const createProject = (data) => api.post('/projects/translation/', data)
export const updateProject = (id, data) => api.put(`/projects/translation/${id}`, data)
export const deleteProject = (id) => api.delete(`/projects/translation/${id}`)
