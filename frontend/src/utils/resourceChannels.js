export const channelColumns = [
  { key: 'name', label: '渠道／平台名称', width: 160 },
  { key: 'category', label: '平台性质', width: 120 },
  { key: 'purpose', label: '平台用途', width: 180 },
  { key: 'maintainers', label: '维护人', width: 140 },
  { key: 'users', label: '使用人', width: 140 },
  { key: 'description', label: '平台情况说明', width: 260 },
  { key: 'created_by_name', label: '创建人', width: 120 },
  { key: 'created_at', label: '创建时间', width: 190 },
  { key: 'updated_by_name', label: '更新人', width: 120 },
  { key: 'updated_at', label: '更新时间', width: 190 },
]
export const defaultChannelColumns = ['name', 'category', 'purpose', 'maintainers', 'users']
export const cleanChannelColumns = value => {
  if (!Array.isArray(value)) throw new Error('字段配置无效')
  return [...new Set(value.filter(key => channelColumns.some(column => column.key === key)))]
}
export const channelMembersText = members => (members || []).map(person => `${person.name}${person.is_active === false ? '（已停用）' : ''}`).join('、') || '-'
export const channelDateTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
export const channelParams = (filters, page, pageSize) => ({
  keyword: filters.keyword.trim() || undefined,
  category: filters.category || undefined,
  maintainer_ids: filters.maintainer_ids.length ? [...filters.maintainer_ids] : undefined,
  user_ids: filters.user_ids.length ? [...filters.user_ids] : undefined,
  skip: (page - 1) * pageSize,
  limit: pageSize,
})
