import api from './index'

export const getClientContacts = (params) => {
  return api.get('/client-contacts/', { params })
}

export const getClientContact = (id) => {
  return api.get(`/client-contacts/${id}`)
}

export const createClientContact = (data) => {
  return api.post('/client-contacts/', data)
}

export const updateClientContact = (id, data) => {
  return api.put(`/client-contacts/${id}`, data)
}

export const deleteClientContact = (id) => {
  return api.delete(`/client-contacts/${id}`)
}
