const scaled = (value, decimals) => BigInt(Number(value).toFixed(decimals).replace('.', ''))
export function quotationLineCents(item, unitDecimals = 4) {
  if (item.quantity == null || item.unit_price == null) return null
  const divisor = 10n ** BigInt(unitDecimals + 2)
  return (scaled(item.quantity, 4) * scaled(item.unit_price, unitDecimals) + divisor / 2n) / divisor
}
export const quotationMoney = cents => {
  const absolute = cents < 0n ? -cents : cents
  return `${cents < 0n ? '-' : ''}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`
}
