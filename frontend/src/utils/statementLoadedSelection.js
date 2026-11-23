// 客户的全部项目已在当前列表中时，生成状态检查复用已加载的 ID，避免再查完整财务树。
export function loadedStatementOrderIds({ rows, total, loadedQuery, currentQuery, months, requireStatement = false }) {
  if (!loadedQuery || JSON.stringify(loadedQuery) !== JSON.stringify(currentQuery)) return null
  if (months.length !== 1 || (months[0] || '') !== (currentQuery.billing_month || '')) return null
  if (!Number.isInteger(total) || total < 0 || rows.length < total) return null
  if (requireStatement && currentQuery.statement_required === false) return null
  return rows.filter(row => !row.fixedPricingFrom && (!requireStatement || row.statementRequired || row.hasStatementRequiredOrders))
    .map(row => row.id)
}
