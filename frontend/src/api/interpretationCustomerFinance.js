import api from './index'
const base='/interpretation-customer-finance'
export const getInterpretationFinancePage=(params,signal)=>api.get(`${base}/page`,{params,signal})
export const getInterpretationFinance=(scope,id)=>api.get(`${base}/${scope}/${id}`)
export const saveInterpretationFinance=(scope,id,data)=>api.put(`${base}/${scope}/${id}`,data)
export const getInterpretationFinanceHistory=(scope,id,page)=>api.get(`${base}/${scope}/${id}/history`,{params:{page}})
export const getInterpretationStatement=(id,params,config={})=>api.get(`${base}/statement/project/${id}`,{...config,params})
