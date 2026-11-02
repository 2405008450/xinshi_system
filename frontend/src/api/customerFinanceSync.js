import api from './index'
export const getCustomerRateDifferences=(module,id,page,signal)=>api.get(`/customer-finance-sync/${module}/${id}/differences`,{params:{page},signal})
export const synchronizeCustomerRates=(module,id,data)=>api.post(`/customer-finance-sync/${module}/${id}/sync`,data)
