import api from './index'
import { isMockEnabled, mockApi } from '../mock'

const useMock = isMockEnabled()

export const getSubsidiaryClients = (params) => {
  if (useMock) {
    return mockApi.subsidiaryClients.get(params)
  }
  return api.get('/subsidiary-clients/', { params })
}

export const getSubsidiaryClient = (id) => {
  if (useMock) {
    return mockApi.subsidiaryClients.getById?.(id) || Promise.resolve(null)
  }
  return api.get(`/subsidiary-clients/${id}`)
}

export const createSubsidiaryClient = (data) => {
  if (useMock) {
    return mockApi.subsidiaryClients.create(data)
  }
  return api.post('/subsidiary-clients/', data)
}

export const updateSubsidiaryClient = (id, data) => {
  if (useMock) {
    return mockApi.subsidiaryClients.update(id, data)
  }
  return api.put(`/subsidiary-clients/${id}`, data)
}

export const deleteSubsidiaryClient = (id) => {
  if (useMock) {
    return mockApi.subsidiaryClients.delete(id)
  }
  return api.delete(`/subsidiary-clients/${id}`)
}
