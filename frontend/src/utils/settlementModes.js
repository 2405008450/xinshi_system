export const translationSettlementModeLabels = {
  individual: '逐笔独立结算',
  monthly: '多单合并结算',
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
