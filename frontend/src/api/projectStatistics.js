import api from './index'

export const getProjectStatistics=(module,params,config={})=>api.get(
  module==='translation'?'/projects/translation/statistics':`/project-statistics/${module}`,
  {...config,params:module==='translation'?params:Object.fromEntries(Object.entries(params).filter(([key])=>key!=='tax_basis'))}
)
