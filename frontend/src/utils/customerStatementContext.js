import { orderStatementMonth } from './statementRequirementMonth.js'

// 列表行和项目表单共用同一客户、订单月份及客户经理上下文。
export function customerStatementContext(project = {}) {
  const month = orderStatementMonth(project.orderNo) || project.billingMonth
  if (!project.clientId || !month) return null
  return {
    id: project.clientId,
    name: project.clientShortName || project.clientName || '客户',
    month,
    manager: project.clientManager,
  }
}
