export const translationSettlementModeLabels = {
  individual: '逐笔独立结算',
  monthly: '多单合并结算',
  sub_client: '子客户合并结算',
  special: '特殊结算',
}

export const settlementModeLabels = {
  ...translationSettlementModeLabels,
  statement: '按对账单结算',
}

export function translationSettlementMode(order) {
  if (order.paymentMethod === 'statement') return 'monthly'
  return order.paymentMethod || (order.hasMonthlyPaymentPeers ? 'monthly' : 'individual')
}

export const isGroupedSettlement = mode => mode === 'monthly' || mode === 'sub_client'
export const settlementModeDisabled = (order, mode) => mode === 'sub_client' && !order.subClientId
