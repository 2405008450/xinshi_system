import api from './index'

export const getTranslationRevenue = (params, config = {}) => api.get('/translation-revenue', {
  timeout: params.period==='all'?120000:30000, ...config, params, paramsSerializer: { indexes: null },
})
