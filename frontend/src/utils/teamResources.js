import { formatBusinessDateTime } from './dateTime.js'

export const teamColumns = [
  { key: 'short_name', label: '团队简称', width: 140 },
  { key: 'full_name', label: '团队全称', width: 180 },
  { key: 'team_type', label: '团队类型', width: 130 },
  { key: 'resource_types', label: '资源类型', width: 180 },
  { key: 'contacts', label: '团队对接人', width: 160 },
  { key: 'introduction', label: '团队简介', width: 220 },
  { key: 'other_resource_description', label: '其他资源说明', width: 180 },
  { key: 'resource_situation', label: '资源情况', width: 220 },
  { key: 'remarks', label: '备注', width: 200 },
  { key: 'contact_user', label: '信实对接人', width: 130 },
  { key: 'contact_date', label: '对接日期', width: 145 },
  { key: 'follow_up_user', label: '信实跟进人', width: 130 },
  { key: 'created_by_name', label: '创建人', width: 110 },
  { key: 'created_at', label: '创建时间', width: 190 },
  { key: 'updated_by_name', label: '修改人', width: 110 },
  { key: 'updated_at', label: '更新时间', width: 190 },
]
export const defaultTeamColumns = ['short_name', 'full_name', 'team_type', 'resource_types', 'contacts', 'contact_user', 'contact_date', 'follow_up_user']
export const cleanTeamColumns = value => {
  if (!Array.isArray(value)) throw new Error('无效字段配置')
  const selected = teamColumns.map(c => c.key).filter(key => value.includes(key))
  const previousDefaults = defaultTeamColumns.filter(key => key !== 'contacts')
  // 旧默认组合补上新列；用户自定义组合和全部隐藏保持原选择。
  return selected.length === previousDefaults.length && previousDefaults.every(key => selected.includes(key)) ? [...defaultTeamColumns] : selected
}
export const personLabel = person => person ? `${person.name}${person.is_active === false ? '（已停用）' : ''}` : '-'
export const emptyTeamContact = () => ({ id: null, name: '', nickname: '', contact_info: '' })
export const cleanTeamContacts = (contacts = [], canViewContacts = true) => contacts
  .filter(item => item.id || item.name?.trim() || item.nickname?.trim() || (canViewContacts && item.contact_info?.trim()))
  .map(item => ({ id: item.id || null, name: (item.name || '').trim(), nickname: (item.nickname || '').trim(), ...(canViewContacts ? { contact_info: (item.contact_info || '').trim() } : {}) }))
export const teamContactSummary = contacts => {
  if (!contacts?.length) return '暂未填写'
  const first = contacts[0].name || contacts[0].nickname || '对接人1'
  return contacts.length > 1 ? `${first} 等${contacts.length}人` : first
}
export const emptyTeam = () => ({ short_name: '', full_name: '', team_type: '', introduction: '', resource_types: [], other_resource_description: '', resource_situation: '', remarks: '', contacts: [], contact_user_id: null, contact_date: null, follow_up_user_id: null, revision: 0 })
export function teamPayload(form, canViewContacts = true) {
  const result = Object.fromEntries(Object.keys(emptyTeam()).map(key => [key, form[key]]))
  result.resource_types = [...new Set(result.resource_types)]
  result.contacts = cleanTeamContacts(form.contacts || [], canViewContacts)
  if (!result.resource_types.includes('other')) result.other_resource_description = ''
  for (const key of ['contact_user_id', 'contact_date', 'follow_up_user_id']) result[key] ||= null
  return result
}
export const emptyTeamFilters = () => ({ keyword: '', team_type: '', resource_types: [], contact_user_id: '', follow_up_user_id: '', contact_dates: [] })
export function teamParams(filters, page, limit) {
  const params = { skip: (page - 1) * limit, limit }
  for (const key of ['keyword', 'team_type', 'contact_user_id', 'follow_up_user_id']) if (filters[key]?.trim()) params[key] = filters[key].trim()
  if (filters.resource_types.length) params.resource_types = [...new Set(filters.resource_types)]
  if (filters.contact_dates?.length === 2) [params.contact_start, params.contact_end] = filters.contact_dates
  return params
}
export function teamDisplay(row, key, options) {
  if (key === 'contacts') return row.contacts?.length ? teamContactSummary(row.contacts) : '-'
  if (key === 'team_type') return options.team_types.find(item => item.value === row[key])?.label || '-'
  if (key === 'resource_types') return (row[key] || []).map(value => options.resource_types.find(item => item.value === value)?.label || value).join('、') || '-'
  if (key === 'contact_user' || key === 'follow_up_user') return personLabel(row[key])
  if (key === 'contact_date') return row[key] ? row[key].replace(/^(\d{4})-(\d{2})-(\d{2})$/, '$1年$2月$3日') : '-'
  if (key.endsWith('_at')) return formatBusinessDateTime(row[key])
  return row[key] || '-'
}
