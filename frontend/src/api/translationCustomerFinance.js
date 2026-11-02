import api from './index'
const camel = value => Array.isArray(value) ? value.map(camel) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([key,item]) => [key.replace(/_([a-z])/g,(_,letter)=>letter.toUpperCase()),camel(item)])) : value
export const getCustomerFinancePage=(params,config={})=>api.get('/translation-customer-finance/page',{...config,params}).then(camel)
export const getCustomerFinanceProject=id=>api.get(`/translation-customer-finance/project/${id}`).then(camel)
export const saveCustomerFinanceProject=(id,data)=>api.put(`/translation-customer-finance/project/${id}`,data).then(camel)
export const getCustomerTranslationRates=id=>api.get(`/customer-translation-rates/${id}`).then(camel)
export const saveCustomerTranslationRates=(id,data)=>api.put(`/customer-translation-rates/${id}`,data).then(camel)
export const getCustomerTranslationRateHistory=(id,params={})=>api.get(`/customer-translation-rates/${id}/history`,{params}).then(camel)
export const getTranslationFinanceHistory=(id,params={},config={})=>api.get(`/translation-customer-finance/project/${id}/history`,{...config,params}).then(camel)
