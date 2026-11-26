import api from './index'
const base='/interpretation-customer-finance/settlement-settings'
export const readOralPreferences=(kind,id,config={})=>api.get(`${base}/${kind}/${id}`,config)
export const saveOralPreferences=(kind,id,data)=>api.put(`${base}/${kind}/${id}`,data)
export const readOralParty=(id,params,signal)=>api.get(`${base}/sub-client/${id}/party`,{params,signal})
export const saveOralParty=(id,data)=>api.put(`${base}/sub-client/${id}/party`,data)
export const readOralPeriodProjects=(id,signal)=>api.get(`${base}/project/${id}/period-projects`,{signal})
export const readOralBillingPeriods=(id,month,signal)=>api.get(`${base}/project/${id}/billing-period`,{params:{month},signal})
export const saveOralBillingPeriod=(id,data)=>api.put(`${base}/project/${id}/billing-period`,data)
