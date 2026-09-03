import api from './index'

export const getProjectOperationAudits = (params, signal) => (
  api.get('/project-operation-audits/', { params, signal })
)
