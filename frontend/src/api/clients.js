import api from './index'
import { isMockEnabled, mockApi } from '../mock'

// 检查是否启用 Mock 模式
const useMock = isMockEnabled()

export const getClients = (params) => {
  if (useMock) {
    return mockApi.clients.get(params)
  }
  return api.get('/clients/', { params })
}

export const getClient = (id) => {
  if (useMock) {
    return mockApi.clients.getById(id)
  }
  return api.get(`/clients/${id}`)
}

export const createClient = (data) => {
  if (useMock) {
    return mockApi.clients.create(data)
  }
  return api.post('/clients/', data)
}

export const updateClient = (id, data) => {
  if (useMock) {
    return mockApi.clients.update(id, data)
  }
  return api.put(`/clients/${id}`, data)
}

export const deleteClient = (id) => {
  if (useMock) {
    return mockApi.clients.delete(id)
  }
  return api.delete(`/clients/${id}`)
}
