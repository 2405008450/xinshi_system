import api from './index'
import { isMockEnabled, mockApi } from '../mock'

const useMock = isMockEnabled()

export const getConsultations = (params) => {
  if (useMock) {
    return mockApi.consultations.get(params)
  }
  return api.get('/consultations/', { params })
}

export const getConsultation = (id) => {
  if (useMock) {
    return mockApi.consultations.getById?.(id) || Promise.resolve(null)
  }
  return api.get(`/consultations/${id}`)
}

export const createConsultation = (data) => {
  if (useMock) {
    return mockApi.consultations.create(data)
  }
  return api.post('/consultations/', data)
}

export const updateConsultation = (id, data) => {
  if (useMock) {
    return mockApi.consultations.update(id, data)
  }
  return api.put(`/consultations/${id}`, data)
}

export const deleteConsultation = (id) => {
  if (useMock) {
    return mockApi.consultations.delete(id)
  }
  return api.delete(`/consultations/${id}`)
}
