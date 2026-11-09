import api from './index'
export const getCustomerTranslationHistory=(params,config={})=>api.get('/projects/translation/customer-history',{...config,params})
