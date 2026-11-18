import { orderStatementMonth } from './statementRequirementMonth.js'

// 列表行和项目表单共用同一客户、订单月份及客户经理上下文。
export function customerStatementContext(project = {}) {
  const month = project.billingMonth || orderStatementMonth(project.orderNo)
  if (!project.clientId || !month) return null
  return {
    id: project.clientId,
    name: project.clientShortName || project.clientName || '客户',
    month,
    manager: project.clientManager,
    ...(project.subClientId && (project.settlementParty === 'sub_client' ||
      (!project.settlementParty && project.paymentMethod === 'sub_client')) ? {
      subClientId: project.subClientId, subClientName: project.subClientShortName,
    } : {}),
    period: project.settlementPeriodNumber,
  }
}
