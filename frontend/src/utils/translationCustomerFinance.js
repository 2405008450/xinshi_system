import { WORD_COUNT_METRICS, normalizeWordCountMatrix } from './wordCountMatrix.js'

const present = value => value !== null && value !== undefined && value !== ''
const money = value => Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const metricName = key => WORD_COUNT_METRICS.find(item => item.key === key)?.shortLabel || key
export function calculateCustomerPrice(amount, quantity, unitSize = 1) {
  if (amount == null || quantity == null) return null
  const scaled = value => {const [whole, fraction='']=String(Number(value)).split('.');return BigInt(whole)*10000n+BigInt(fraction.padEnd(4,'0').slice(0,4))}
  const divisor=scaled(unitSize)
  if(divisor<=0n)return null
  const numerator=scaled(amount)*BigInt(quantity)*100n
  const cents=(numerator+divisor/2n)/divisor
  return `${cents/100n}.${String(cents%100n).padStart(2,'0')}`
}
export function customerFinanceWordCount(project) {
  const values = normalizeWordCountMatrix(project.wordCountMatrix).customer
  return WORD_COUNT_METRICS.filter(item => present(values[item.key])).map(item => `${item.shortLabel}：${values[item.key].toLocaleString('zh-CN')}`).join('；') || '-'
}
export function customerFinanceUnitPrices(project) {
  return (project.customerChargeItems || []).map(item => {
    if (item.pricingMode === 'fixed') return `${item.itemName}：固定收费`
    const values = [['不含税', item.unitPriceExclTax ?? item.unitPrice], ['含税', item.unitPriceInclTax]]
      .filter(([, value]) => present(value)).map(([label, value]) => `${label} ${item.currency || 'CNY'} ${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 4 })}/${item.unitSize || 1000}${metricName(item.metricType)}`)
    return `${item.itemName}：${values.join('；') || '未填写'}`
  }).join('\n') || '-'
}
// 汇总使用接口由 Decimal 计算的建议金额，不在页面重新计算财务金额。
export function customerFinanceTotals(project, adjusted = false) {
  const groups = new Map()
  for (const item of project.customerChargeItems || []) {
    for (const [kind, label] of [['Excl', '不含税'], ['Incl', '含税']]) {
      const original = item[`calculatedTotal${kind}Tax`] ?? (kind === 'Excl' ? item.calculatedAmount : null)
      const recorded = item[`total${kind}Tax`] ?? (kind === 'Excl' ? item.amountOverride ?? item.finalAmount : null)
      const value = adjusted || item.pricingMode === 'fixed' ? recorded ?? original : original
      if (!present(value)) continue
      const key = `${item.currency || 'CNY'}（${label}）`
      // 按分相加，避免二进制浮点累加出现尾差。
      const group = groups.get(key) || { cents: 0, count: 0, currency: item.currency || 'CNY' }
      group.cents += Math.round(Number(value) * 100); group.count++
      groups.set(key, group)
    }
  }
  return [...groups].map(([label, group]) => {
    const count = (project.customerChargeItems || []).filter(item => (item.currency || 'CNY') === group.currency).length
    return `${label} ${money(group.cents / 100)}${group.count < count ? `（已填 ${group.count}/${count} 项）` : ''}`
  }).join('\n') || '-'
}
export function customerFinanceNotes(project) {
  return (project.customerChargeItems || []).filter(item => item.remarks?.trim()).map(item => `${item.itemName}：${item.remarks}`).join('\n') || '-'
}
export function customerFinanceChargePayload(items) {
  const keys = ['id','sequenceNo','itemName','pricingMode','metricType','unitSize','billingMonth','unitPriceExclTax','unitPriceInclTax','totalExclTax','totalInclTax','currency','remarks']
  return items.map((item, index) => Object.fromEntries(keys.map(key => [key, key === 'sequenceNo' ? index + 1 : item[key] ?? null])))
}
