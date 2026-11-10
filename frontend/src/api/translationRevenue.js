import api from './index'

export const getTranslationRevenue = (params, config = {}) => api.get('/translation-revenue', {
  ...config, params, paramsSerializer: { indexes: null },
})
