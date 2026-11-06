const scaled = value => BigInt(Number(value).toFixed(4).replace('.', ''))
export function quotationLineCents(item) {
  if (item.quantity == null || item.unit_price == null) return null
  return (scaled(item.quantity) * scaled(item.unit_price) + 500000n) / 1000000n
}
export const quotationMoney = cents => `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`
