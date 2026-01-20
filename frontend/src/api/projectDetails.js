import api from './index'

export const getProjectDetails = (params) => api.get('/project-details/', { params })
export const getProjectDetail = (id) => api.get(`/project-details/${id}`)
export const createProjectDetail = (data) => api.post('/project-details/', data)
export const updateProjectDetail = (id, data) => api.put(`/project-details/${id}`, data)
export const deleteProjectDetail = (id) => api.delete(`/project-details/${id}`)
