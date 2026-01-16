import api from './index'

export const getProjectFiles = (params) => api.get('/project-files/', { params })
export const getProjectFilesByProject = (projectId, params) => 
  api.get(`/project-files/project/${projectId}`, { params })
export const getProjectFile = (id) => api.get(`/project-files/${id}`)
export const createProjectFile = (data) => api.post('/project-files/', data)
export const updateProjectFile = (id, data) => api.put(`/project-files/${id}`, data)
export const deleteProjectFile = (id) => api.delete(`/project-files/${id}`)
