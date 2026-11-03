import api from './index'

const base = clientId => `/clients/${clientId}/annotation-rates`
export const getCustomerAnnotationRates = (clientId, config = {}) => api.get(base(clientId), config)
export const createCustomerAnnotationRate = (clientId, data) => api.post(base(clientId), data)
export const updateCustomerAnnotationRate = (clientId, id, data) => api.put(`${base(clientId)}/${id}`, data)
export const deleteCustomerAnnotationRate = (clientId, row) => api.delete(`${base(clientId)}/${row.id}`, { params: { revision: row.revision } })
