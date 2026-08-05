import api from './index'

export const getClients = (params, config = {}) => {
  return api.get('/clients/', { ...config, params })
}

export const getClientCount = (params, config = {}) => {
  return api.get('/clients/count', { ...config, params })
}

export const getClient = (id) => {
  return api.get(`/clients/${id}`)
}

export const createClient = (data) => {
  return api.post('/clients/', data)
}

export const updateClient = (id, data) => {
  return api.put(`/clients/${id}`, data)
}

export const deleteClient = (id) => {
  return api.delete(`/clients/${id}`)
}

export const createSubClient = (clientId, data) => {
  return api.post(`/clients/${clientId}/sub_clients`, data)
}

export const updateSubClient = (subId, data) => {
  return api.put(`/clients/sub_clients/${subId}`, data)
}

export const deleteSubClient = (subId) => {
  return api.delete(`/clients/sub_clients/${subId}`)
}
