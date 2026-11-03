const fields = ['unitPriceExclTax', 'unitPriceInclTax', 'totalExclTax', 'totalInclTax']
const snake = value => value.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
export const taxPriceForm = value => Object.fromEntries(fields.map(key => {
  const amount = value?.[key] ?? value?.[snake(key)]
  return [key, amount == null || amount === '' ? undefined : Number(amount)]
}))
export const taxPricePayload = value => Object.fromEntries(fields.map(key => [snake(key), value?.[key] ?? null]))
export const taxUnitAmount = (tax, original) => tax?.unitPriceExclTax ?? tax?.unitPriceInclTax ?? original
export const taxPriceSummary = (value, currency = 'CNY', unit = '', totals = true) => {
  const values = taxPriceForm(value)
  return fields.filter(key => totals || key.startsWith('unit')).flatMap((key, index) => values[key] == null ? [] : [
    `${['不含税单价', '含税单价', '不含税总价', '含税总价'][index]}：${currency} ${values[key]}${key.startsWith('unit') && unit ? '/' + unit : ''}`,
  ]).join('\n')
}
