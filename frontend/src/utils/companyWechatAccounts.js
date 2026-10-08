export const companyWechatAccounts = [
  ...Array.from({ length: 6 }, (_, i) => `HR${i + 1}`),
  ...Array.from({ length: 6 }, (_, i) => `HR${i + 1}企微`),
]
export const deletedWechatMarkers = ['已删微信', '已删企微']
// 历史字符串整体作为一个值，不猜测拆分自定义账号名称。
export const normalizeWechatAccounts = (values, legacy = '') => {
  const items = Array.isArray(values) ? values : [typeof values === 'string' ? values : legacy]
  return [...new Set(items.map(value => String(value || '').trim()).filter(Boolean))]
}
export const formatWechatAccounts = (values, legacy = '') => normalizeWechatAccounts(values, legacy).join('、')
export const sameWechatAccounts = (left, right) => {
  const a = normalizeWechatAccounts(left), b = normalizeWechatAccounts(right)
  return a.length === b.length && a.every(value => b.includes(value))
}
