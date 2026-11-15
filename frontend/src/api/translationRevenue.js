import api from './index'

export const getTranslationRevenue = (params, config = {}) => api.get('/translation-revenue', {
  timeout: 30000, ...config, params, paramsSerializer: { indexes: null },
})
