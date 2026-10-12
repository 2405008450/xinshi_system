import { formatBusinessDateTime } from './dateTime.js'

export const channelPopoverOptions = {
  modifiers: [{ name: 'preventOverflow', options: { rootBoundary: 'viewport', padding: 16, tether: false, altAxis: true } }],
}

export const channelColumns = [
  { key: 'name', label: '渠道／平台名称', width: 140 },
  { key: 'category', label: '平台性质', width: 100 },
  { key: 'purpose', label: '平台用途', width: 180 },
  { key: 'maintainers', label: '维护人', width: 90 },
  { key: 'users', label: '使用人', width: 90 },
  { key: 'description', label: '平台情况说明', width: 260 },
  { key: 'created_by_name', label: '创建人', width: 120 },
  { key: 'created_at', label: '创建时间', width: 190 },
  { key: 'updated_by_name', label: '更新人', width: 120 },
  { key: 'updated_at', label: '更新时间', width: 190 },
]
export const defaultChannelColumns = ['name', 'category', 'purpose', 'maintainers', 'users', 'description']
export const cleanChannelColumns = value => {
  if (!Array.isArray(value)) throw new Error('字段配置无效')
  return [...new Set(value.filter(key => channelColumns.some(column => column.key === key)))]
}
export const channelMembersText = members => (members || []).map(person => `${person.name}${person.is_active === false ? '（已停用）' : ''}`).join('、') || '-'
export const channelDateTime = formatBusinessDateTime
export const aggregateChannelMembers = (accounts, role) => {
  const people = new Map()
  for (const account of accounts || []) for (const person of account[role] || []) people.set(person.id, person)
  return [...people.values()].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN') || a.id.localeCompare(b.id))
}
export const channelParams = (filters, page, pageSize) => ({
  keyword: filters.keyword.trim() || undefined,
  category: filters.category || undefined,
  maintainer_ids: filters.maintainer_ids.length ? [...filters.maintainer_ids] : undefined,
  user_ids: filters.user_ids.length ? [...filters.user_ids] : undefined,
  skip: (page - 1) * pageSize,
  limit: pageSize,
})
