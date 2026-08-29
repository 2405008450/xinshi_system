import api from './index'
import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'

const contactCreateState = { key: '', signature: '' }

export const getClientContacts = (params) => {
  return api.get('/client-contacts/', { params })
}

export const getClientContactCount = () => {
  return api.get('/client-contacts/count')
}

export const getClientContact = (id) => {
  return api.get(`/client-contacts/${id}`)
}

export const createClientContact = async (data) => {
  const key = resolveIdempotencyKey(contactCreateState, data)
  const response = await api.post('/client-contacts/', data, {
    headers: { 'X-Idempotency-Key': key },
  })
  clearIdempotencyKey(contactCreateState, key)
  return response
}

export const updateClientContact = (id, data) => {
  return api.put(`/client-contacts/${id}`, data)
}

export const deleteClientContact = (id) => {
  return api.delete(`/client-contacts/${id}`)
}
