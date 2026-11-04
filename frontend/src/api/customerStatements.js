import api from './index'
export const getStatementPreference=(id,config={})=>api.get(`/clients/${id}/statement-preference`,config)
export const saveStatementPreference=(id,data)=>api.put(`/clients/${id}/statement-preference`,data)
export const getStatementSettings=()=>api.get('/customer-statement-settings')
export const saveStatementSettings=data=>api.put('/customer-statement-settings',data)
export const getStatement=(params,config={})=>api.get('/translation-statements/preview',{...config,params})
export const exportStatement=params=>api.get('/translation-statements/excel',{params,responseType:'blob'})
