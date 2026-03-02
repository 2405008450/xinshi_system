import api from './index'

export const getTranslators = (params) => {
  return api.get('/translators/', { params })
}

export const getTranslator = (id) => {
  return api.get(`/translators/${id}`)
}

export const createTranslator = (data) => {
  return api.post('/translators/', data)
}

export const updateTranslator = (id, data) => {
  return api.put(`/translators/${id}`, data)
}

export const deleteTranslator = (id) => {
  return api.delete(`/translators/${id}`)
}
