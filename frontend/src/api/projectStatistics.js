import api from './index'

export const getProjectStatistics=(module,params,config={})=>api.get(
  `/project-statistics/${module}`,
  // 完整历史统计包含跨业务客户及项目金额汇总，使用独立于普通列表的超时。
  {timeout:60000,...config,params}
)
