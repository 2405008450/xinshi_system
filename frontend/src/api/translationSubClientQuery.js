import api from './index'

export const getTranslationSubClientCustomers = (params, signal) =>
  api.get('/projects/translation/sub-client-projects', { params, signal })

export const getTranslationSubClientOrders = (params, signal) =>
  api.get('/projects/translation/sub-client-projects/orders', { params, signal })
