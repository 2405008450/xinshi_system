import api from './index'

export const getSubsidiaryClients = (params) => {
  return api.get('/subsidiary-clients/', { params })
}

export const getSubsidiaryClient = (id) => {
  return api.get(`/subsidiary-clients/${id}`)
}

export const createSubsidiaryClient = (data) => {
  return api.post('/subsidiary-clients/', data)
}

export const updateSubsidiaryClient = (id, data) => {
  return api.put(`/subsidiary-clients/${id}`, data)
}

export const deleteSubsidiaryClient = (id) => {
  return api.delete(`/subsidiary-clients/${id}`)
}
