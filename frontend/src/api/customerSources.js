import api from './index'

const endpoint = clientId => clientId ? `/clients/${clientId}/sources` : '/data-analysis/customer-sources'
export const getCustomerSourceSummary = (clientId, params, config = {}) => api.get(endpoint(clientId), { ...config, params })
export const getCustomerSourceRecords = (clientId, params, config = {}) => api.get(`${endpoint(clientId)}/records`, { ...config, params })
