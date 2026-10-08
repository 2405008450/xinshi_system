export const referralColumns = [
  { key: 'work_date', label: '推广日期', width: 140 },
  { key: 'full_name', label: '推荐人', width: 150 },
  { key: 'wechat', label: '微信', width: 160 },
  { key: 'amount', label: '金额（元）', width: 120 },
  { key: 'payment_status', label: '付款状态', width: 110 },
  { key: 'payment_date', label: '付款日期', width: 140 },
  { key: 'pull_description', label: '拉人说明', width: 200 },
  { key: 'moments_description', label: '发圈说明', width: 200 },
  { key: 'groups_description', label: '发群说明', width: 200 },
  { key: 'remarks', label: '备注', width: 200 },
  { key: 'created_by_name', label: '录入人', width: 120 },
  { key: 'created_at', label: '录入时间', width: 190 },
  { key: 'updated_by_name', label: '最近操作人', width: 120 },
  { key: 'updated_at', label: '操作时间', width: 190 },
]
export const defaultReferralColumns = ['work_date', 'full_name', 'amount', 'payment_status', 'payment_date', 'updated_by_name', 'updated_at']
export const imageCategories = [
  { key: 'pull', label: '拉人凭证', hint: '参考奖励：3元' },
  { key: 'moments', label: '发圈凭证', hint: '参考奖励：5元' },
  { key: 'groups', label: '发群凭证', hint: '参考奖励：5元' },
  { key: 'qr', label: '微信收款码', hint: '保留一张当前收款码，上传后替换旧图' },
]
export const today = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date())
export const dateText = value => {
  if (!value) return '-'
  const [y, m, d] = String(value).slice(0, 10).split('-')
  return `${y}年${m}月${d}日`
}
export const timeText = value => value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '-'
export const displayReferralValue = (row, key) => {
  const value = row[key]
  if (['work_date', 'payment_date'].includes(key)) return dateText(value)
  if (['created_at', 'updated_at'].includes(key)) return timeText(value)
  if (key === 'amount') return value === null || value === undefined ? '-' : Number(value).toFixed(2)
  if (key === 'payment_status') return value ? value === 'paid' ? '已支付' : '未支付' : '-'
  return value === null || value === undefined || value === '' ? '-' : String(value)
}
export const cleanReferralColumns = value => {
  if (!Array.isArray(value)) throw new Error('字段配置无效')
  const valid = new Set(referralColumns.map(c => c.key))
  return [...new Set(value.filter(k => typeof k === 'string' && valid.has(k)))]
}
export const auditLabels = { create: '新增', update: '修改', payment: '付款登记／更正', image_add: '添加图片', image_replace: '替换收款码', image_delete: '删除图片', delete: '删除记录' }
export const auditChanges = entry => {
  const keys = new Set([...Object.keys(entry.before || {}), ...Object.keys(entry.after || {})])
  return [...keys].filter(key => referralColumns.some(c => c.key === key) && JSON.stringify(entry.before?.[key]) !== JSON.stringify(entry.after?.[key]))
    .map(key => ({ key, label: referralColumns.find(c => c.key === key).label,
      before: displayReferralValue(entry.before || {}, key), after: displayReferralValue(entry.after || {}, key) }))
}
