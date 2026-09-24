export const developmentColumns = [
  ['platform_name', '开拓平台', 140], ['full_name', '姓名', 110], ['language_names', '语种/方言', 140], ['owner_name', '开拓人', 120],
  ['account_name', '对接账号', 130],
  ['wechat_status', '微信', 140], ['enterprise_status', '企微', 140],
  ['group_status', '进群', 140], ['communication_status', '沟通', 140], ['project_status', '入项', 140],
  ['latest_follow_up', '最近跟进', 200], ['greeting_no', '招呼编号', 190],
  ['phone', '资源手机', 150], ['wechat', '资源微信号', 150], ['resource_code', '资源编号', 160],
  ['work_date', '日期', 130], ['follow_up', '后续跟进', 240], ['remarks', '备注', 240], ['updated_at', '更新时间', 190],
].map(([key, label, width]) => ({ key, label, width }))
export const defaultDevelopmentColumns = developmentColumns.slice(0, 11).map(c => c.key)
export const progressChannels = { wechat: '微信', enterprise: '企微', group: '进群', communication: '沟通', project: '入项' }
export const progressColumnChannel = { wechat_status: 'wechat', enterprise_status: 'enterprise', group_status: 'group', communication_status: 'communication', project_status: 'project' }
export const progressStatuses = channel => ({ group: ['未处理', '已邀进群', '已进群'], communication: ['未处理', '已沟通'], project: ['未处理', '已入项'] })[channel] || statusOptions
export const progressText = (row, channel) => {
  const p = row.progress?.[channel]
  return p ? `${p.status} · ${p.action_date ? p.action_date.slice(5) : '原表未填日期'} · ${p.operator_name}` : '未处理'
}
export const continueDevelopmentValues = form => Object.fromEntries(['platform_id', 'work_date', 'owner_id', 'account_id'].map(key => [key, form[key]]))
// 只保留本次浏览器会话、当天的批次设置，不缓存姓名或联系方式。
export const restoreDevelopmentBatch = (saved, options, today = dateText(new Date())) => {
  if (!saved || saved.day !== today || saved.user_id !== options.user_id) return {}
  const value = saved.batch || {}, result = {}
  if (options.options.some(o => o.kind === 'platform' && o.id === value.platform_id)) result.platform_id = value.platform_id
  if (options.options.some(o => o.kind === 'account' && o.id === value.account_id)) result.account_id = value.account_id
  if ((options.can_delegate || value.owner_id === options.user_id) && options.users.some(u => u.id === value.owner_id)) result.owner_id = value.owner_id
  if (/^\d{4}-\d{2}-\d{2}$/.test(value.work_date || '')) result.work_date = value.work_date
  return result
}
export const dateText = value => {
  const d = new Date(value)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
export const recentDays = (today = new Date()) => {
  const start = new Date(today); start.setDate(start.getDate() - 2)
  return [dateText(start), dateText(today)]
}
export const previousWorkday = (today = new Date()) => {
  const d = new Date(today); d.setDate(d.getDate() - 1)
  while ([0, 6].includes(d.getDay())) d.setDate(d.getDate() - 1)
  return dateText(d)
}
// 局域网 HTTP 页面也能生成 UUID，不依赖仅安全上下文可用的 randomUUID。
export const newDevelopmentId = () => {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
export const cleanColumns = value => {
  const oldDefault = ['platform_name', 'greeting_no', 'full_name', 'language_names', 'owner_name', 'account_name', 'wechat_status', 'enterprise_status']
  if (!Array.isArray(value) || JSON.stringify(value) === JSON.stringify(oldDefault)) return [...defaultDevelopmentColumns]
  return developmentColumns.filter(c => value.includes(c.key)).map(c => c.key)
}
export const statusOptions = ['未处理', '搜不到', '已发请求', '已添加']
export const categoryOptions = [{ value: 'national', label: '全国性平台' }, { value: 'local', label: '地方性平台' }, { value: 'international', label: '国外平台' }]

export const defaultProgressStatus = channel => channel === 'group' ? '已邀进群' : progressStatuses(channel).at(-1)
// 与后端保持相同的渠道、成功状态和变更判断；历史原标记不参与自动入库。
export const hasNewPrivateEntry = (actions, previous = []) => {
  const statuses = { wechat: '已添加', enterprise: '已添加', group: '已进群' }
  const old = new Map(previous.map(a => [a.id, a]))
  const latest = new Map(actions.map(a => [a.channel, a.status]))
  return actions.some(a => statuses[a.channel] === a.status && latest.get(a.channel) === a.status &&
    (!old.has(a.id) || old.get(a.id).channel !== a.channel || old.get(a.id).status !== a.status))
}
