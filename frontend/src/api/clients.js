import api from './index'

export const getClients = (params) => {
  return api.get('/clients/', { params })
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
