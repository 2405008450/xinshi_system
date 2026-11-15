export function financeOrderLevel(order = {}) {
  const suffix = (order.orderNo || '').match(/(?:\.\d+)+$/)?.[0]
  const level = suffix ? suffix.split('.').length - 1 : 0
  if (level) return `${['', '一', '二', '三', '四', '五'][level] || level}级子订单`
  return order.hasChildren || order.childOrderCount || order.children?.length ? '母订单' : ''
}
