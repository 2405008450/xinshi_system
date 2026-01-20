import api from './index'
import { isMockEnabled, mockApi } from '../mock'

const useMock = isMockEnabled()

export const getClientContacts = (params) => {
  if (useMock) {
    return mockApi.clientContacts.get(params)
  }
  return api.get('/client-contacts/', { params })
}

export const getClientContact = (id) => {
  if (useMock) {
    return mockApi.clientContacts.getById?.(id) || Promise.resolve(null)
  }
  return api.get(`/client-contacts/${id}`)
}

export const createClientContact = (data) => {
  if (useMock) {
    return mockApi.clientContacts.create(data)
  }
  return api.post('/client-contacts/', data)
}

export const updateClientContact = (id, data) => {
  if (useMock) {
    return mockApi.clientContacts.update(id, data)
  }
  return api.put(`/client-contacts/${id}`, data)
}

export const deleteClientContact = (id) => {
  if (useMock) {
    return mockApi.clientContacts.delete(id)
  }
  return api.delete(`/client-contacts/${id}`)
}
