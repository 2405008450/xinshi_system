import api from './index'
export const getCustomerRateDifferences=(module,id,page,signal,subClientId)=>api.get(`/customer-finance-sync/${module}/${id}/differences`,{
  params:{page,group_orders:module==='translation'||undefined,sub_client_id:subClientId||undefined},signal,
})
export const synchronizeCustomerRates=(module,id,data)=>api.post(`/customer-finance-sync/${module}/${id}/sync`,data)
