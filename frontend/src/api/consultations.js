import api from './index'

export const getConsultations = (params) => {
  return api.get('/consultations/', { params })
}

export const getConsultation = (id) => {
  return api.get(`/consultations/${id}`)
}

export const createConsultation = (data) => {
  return api.post('/consultations/', data)
}

export const updateConsultation = (id, data) => {
  return api.put(`/consultations/${id}`, data)
}

export const deleteConsultation = (id) => {
  return api.delete(`/consultations/${id}`)
}
