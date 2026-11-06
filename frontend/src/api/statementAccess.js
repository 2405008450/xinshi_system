import api from './index'
export const getStatementAccess=()=>api.get('/statement-access/context')
export const getStatementAccessConfiguration=()=>api.get('/statement-access/configuration')
export const saveStatementGrant=data=>api.put('/statement-access/grant',data)
export const getStatementGrantHistory=(params={})=>api.get('/statement-access/history',{params})
export const getCrossStatementClients=()=>api.get('/statement-reorganization/clients')
export const getCrossStatementWorkspaces=(ids,config={})=>api.get('/statement-reorganization/workspaces',{...config,params:{client_ids:ids},paramsSerializer:{indexes:null}})
export const reorganizeCrossStatements=data=>api.post('/statement-reorganization/apply',data)

export const saveStatementGrantsBatch=data=>api.put('/statement-access/grants/batch',data)

export const previewMergedProjects=data=>api.post('/statement-reorganization/project-preview',data)
export const generateMergedProjects=data=>api.post('/statement-reorganization/generate-projects',data)
