import api from './index'
import { isMockEnabled, mockApi } from '../mock'

const useMock = isMockEnabled()

export const getTranslators = (params) => {
  if (useMock) {
    return mockApi.translators.get(params)
  }
  return api.get('/translators/', { params })
}

export const getTranslator = (id) => {
  if (useMock) {
    return mockApi.translators.getById(id)
  }
  return api.get(`/translators/${id}`)
}

export const createTranslator = (data) => {
  if (useMock) {
    return mockApi.translators.create(data)
  }
  return api.post('/translators/', data)
}

export const updateTranslator = (id, data) => {
  if (useMock) {
    return mockApi.translators.update(id, data)
  }
  return api.put(`/translators/${id}`, data)
}

export const deleteTranslator = (id) => {
  if (useMock) {
    return mockApi.translators.delete(id)
  }
  return api.delete(`/translators/${id}`)
}
