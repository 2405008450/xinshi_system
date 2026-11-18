import api from './index'
const base='/interpretation-customer-finance'
export const getInterpretationFinancePage=(params,signal)=>api.get(`${base}/page`,{params,signal})
export const getInterpretationFinance=(scope,id,signal)=>api.get(`${base}/${scope}/${id}`,{signal,savedSyncReplay:true})
export const saveInterpretationFinance=(scope,id,data)=>api.put(`${base}/${scope}/${id}`,data)
export const saveInterpretationSettlementMode=(id,data)=>api.patch(`${base}/settlement/project/${id}`,data)
export const getInterpretationFinanceHistory=(scope,id,page,signal)=>api.get(`${base}/${scope}/${id}/history`,{params:{page},signal,savedSyncReplay:true})
export const getInterpretationStatement=(id,params,config={})=>api.get(`${base}/statement/project/${id}`,{...config,params})
export const getInterpretationInvoice=(id,config={})=>api.get(`${base}/invoice/project/${id}`,config)
export const saveInterpretationInvoice=(id,data)=>api.put(`${base}/invoice/project/${id}`,data)
