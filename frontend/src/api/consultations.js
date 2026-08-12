import api from './index'

export const getConsultations = (params, config = {}) => {
  return api.get('/consultations/', { ...config, params })
}

export const getConsultationCount = (params, config = {}) => {
  return api.get('/consultations/count', { ...config, params })
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

export const createProjectFromConsultation = (id, projectName) => {
  return api.post(`/consultations/${id}/create-project`, { project_name: projectName })
}

export const previewConfirmation = (data) => {
  return api.post('/consultations/confirmation-preview', data)
}

export const createConfirmedConsultation = (consultation, confirmation) => {
  return api.post('/consultations/confirm', { consultation, confirmation })
}

export const updateConfirmedConsultation = (id, consultation, confirmation) => {
  return api.post(`/consultations/${id}/confirm`, { consultation, confirmation })
}
