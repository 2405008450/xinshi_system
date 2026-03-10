import api from './index'

export const getFinanceRecords = (params) => {
  return api.get('/finance/', { params })
}

export const getFinanceCount = (params) => {
  return api.get('/finance/count', { params })
}

export const getFinanceRecord = (id) => {
  return api.get(`/finance/${id}`)
}

export const getFinanceByProject = (projectId) => {
  return api.get(`/finance/by-project/${projectId}`)
}

export const createFinanceRecord = (data) => {
  return api.post('/finance/', data)
}

export const updateFinanceRecord = (id, data) => {
  return api.put(`/finance/${id}`, data)
}

export const deleteFinanceRecord = (id) => {
  return api.delete(`/finance/${id}`)
}

// 辅助下拉数据
export const getUsers = (params) => {
  return api.get('/users/', { params })
}

export const getProjects = (params) => {
  return api.get('/projects/translation/', { params })
}

export const getClients = (params) => {
  return api.get('/clients/', { params })
}
