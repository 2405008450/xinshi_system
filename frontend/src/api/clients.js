import api from './index'
import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'

const clientCreateState = { key: '', signature: '' }
const subClientCreateState = { key: '', signature: '' }

export const getClients = (params, config = {}) => {
  return api.get('/clients/', { ...config, params })
}

export const getClientCount = (params, config = {}) => {
  return api.get('/clients/count', { ...config, params })
}

export const getClientPage = (params, config = {}) => api.get('/clients/page', { ...config, params })
export const getClientOptions = (params = {}, config = {}) => api.get('/clients/options', { ...config, params })

export const getClient = (id) => {
  return api.get(`/clients/${id}`)
}

export const createClient = async (data) => {
  const key = resolveIdempotencyKey(clientCreateState, data)
  const response = await api.post('/clients/', data, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(clientCreateState, key)
  return response
}

export const updateClient = (id, data) => {
  return api.put(`/clients/${id}`, data)
}

export const deleteClient = (id) => {
  return api.delete(`/clients/${id}`)
}

export const createSubClient = async (clientId, data) => {
  const key = resolveIdempotencyKey(subClientCreateState, { clientId, data })
  const response = await api.post(`/clients/${clientId}/sub_clients`, data, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(subClientCreateState, key)
  return response
}

export const updateSubClient = (subId, data) => {
  return api.put(`/clients/sub_clients/${subId}`, data)
}

export const deleteSubClient = (subId) => {
  return api.delete(`/clients/sub_clients/${subId}`)
}
