import api from './index'
export const previewStatementProjects=data=>api.post('/translation-customer-finance/statement-preview',data)
export const getStatementPreference=(id,config={})=>api.get(`/clients/${id}/statement-preference`,config)
export const saveStatementPreference=(id,data)=>api.put(`/clients/${id}/statement-preference`,data)
export const getStatementSettings=()=>api.get('/customer-statement-settings')
export const saveStatementSettings=data=>api.put('/customer-statement-settings',data)
export const getStatement=(params,config={})=>api.get('/translation-statements/preview',{...config,params})
export const exportStatement=params=>api.get('/translation-statements/excel',{params,responseType:'blob'})
export const getStatementWorkspace=(projectId,mode,config={})=>api.get(`/translation-statement-workspaces/project/${projectId}`,{...config,params:{mode}})
export const getClientStatementWorkspace=(clientId,mode,config={})=>api.get(`/translation-statement-workspaces/${clientId}`,{...config,params:{mode}})
export const importStatementMonths=(data,mode)=>api.post('/translation-statement-workspaces/import',data,{params:{mode}})
export const changeStatementWorkspace=(clientId,data,mode)=>api.post(`/translation-statement-workspaces/${clientId}/actions`,data,{params:{mode}})
export const getStatementWorkspaceHistory=(clientId,params,config={})=>api.get(`/translation-statement-workspaces/${clientId}/history`,{...config,params})
export const exportStatementWorkspace=(clientId,params)=>api.get(`/translation-statement-workspaces/${clientId}/excel`,{params,paramsSerializer:{indexes:null},responseType:'blob'})

export const getStatementWorkspaceHistoryEntry=(clientId,id)=>api.get(`/translation-statement-workspaces/${clientId}/history/${id}`)

export const exportStatementWorkspacePdf=(clientId,params)=>api.get(`/translation-statement-workspaces/${clientId}/pdf`,{params,paramsSerializer:{indexes:null},responseType:'blob'})
