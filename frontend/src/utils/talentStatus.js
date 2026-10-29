export const talentStatusOptions = [
  { value: 'standby', label: '备用' },
  { value: 'active', label: '活跃' },
  { value: 'dormant', label: '休眠' },
  { value: 'blacklisted', label: '黑名单' },
  { value: 'pending_activation', label: '待激活' },
  { value: 'under_observation', label: '待观察' },
]

// 保留历史停用档案的展示，不再提供选择入口。
export const talentStatusLabels = Object.fromEntries([
  ...talentStatusOptions.map(({ value, label }) => [value, label]),
  ['inactive', '停用'],
])
export const talentStatusLabel = value => talentStatusLabels[value] || value || '-'
export const talentStatusType = value => ({
  active: 'success', standby: 'info', dormant: 'info', blacklisted: 'danger',
  pending_activation: 'warning', under_observation: 'warning', inactive: 'danger',
}[value] || 'info')
