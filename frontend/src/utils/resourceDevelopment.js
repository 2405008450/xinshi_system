export const developmentColumns = [
  ['platform_name', '开拓平台', 140], ['full_name', '姓名', 110], ['language_names', '语种/方言', 140],
  ['wechat', '资源微信号', 150], ['xiaohongshu', '资源小红书号', 150], ['owner_name', '开拓人', 120],
  ['account_name', '交换账号', 130],
  ['friend_accounts_text', '加微账号', 180],
  ['wechat_status', '添加微信', 140], ['enterprise_status', '添加企微', 140],
  ['latest_follow_up', '后续跟进情况', 320],
  ['group_status', '企微小群', 180], ['group_large_status', '企微大群', 180], ['communication_status', '沟通', 140], ['project_status', '入项', 140],
  ['greeting_no', '招呼编号', 190],
  ['phone', '资源手机', 150], ['resource_code', '资源编号', 160],
  ['work_date', '日期', 130], ['remarks', '备注', 240], ['updated_at', '更新时间', 190],
].map(([key, label, width]) => ({ key, label, width }))
export const defaultDevelopmentColumns = [
  'platform_name', 'full_name', 'language_names', 'wechat', 'xiaohongshu', 'owner_name',
  'account_name', 'friend_accounts_text', 'wechat_status', 'enterprise_status', 'latest_follow_up',
  'group_status', 'group_large_status', 'communication_status', 'project_status',
]
export const progressChannels = { wechat: '添加微信', enterprise: '添加企微', group: '企微小群', group_large: '企微大群', communication: '沟通', project: '入项' }
export const progressColumnChannel = { wechat_status: 'wechat', enterprise_status: 'enterprise', group_status: 'group', group_large_status: 'group_large', communication_status: 'communication', project_status: 'project' }
export const isGroupChannel = channel => ['group', 'group_large'].includes(channel)
export const groupStatusLabel = (status, channel) => channel === 'group' && status === '已邀进群' ? '已拉群' : status
export const progressStatuses = channel => ({ group: ['未处理', '已拉群', '已进群', '已退群'], group_large: ['未处理', '已拉群', '已发码', '已进群', '已退群'], communication: ['未处理', '已沟通'], project: ['未处理', '已入项'] })[channel] || statusOptions
export const progressText = (row, channel) => {
  const p = row.progress?.[channel]
  return p ? `${groupStatusLabel(p.status, channel)} · ${p.action_date ? p.action_date.slice(5) : '原表未填日期'} · ${p.operator_name}${p.synchronized ? ' · 联系状态同步' : ''}` : '未处理'
}
export const continueDevelopmentValues = form => ({ ...Object.fromEntries(['platform_id', 'work_date', 'owner_id', 'account_id'].map(key => [key, form[key]])), ...(Array.isArray(form.friend_accounts) ? { friend_accounts: [...form.friend_accounts] } : {}) })
// 只保留本次浏览器会话、当天的批次设置，不缓存姓名或联系方式。
export const restoreDevelopmentBatch = (saved, options, today = dateText(new Date())) => {
  if (!saved || saved.day !== today || saved.user_id !== options.user_id) return {}
  const value = saved.batch || {}, result = {}
  if (options.options.some(o => o.kind === 'platform' && o.id === value.platform_id)) result.platform_id = value.platform_id
  if (options.options.some(o => o.kind === 'account' && o.id === value.account_id)) result.account_id = value.account_id
  if (Array.isArray(value.friend_accounts)) result.friend_accounts = [...new Set(value.friend_accounts.filter(item => typeof item === 'string' && item.trim() && item.length <= 100 && !['已删微信', '已删企微'].includes(item)).map(item => item.trim()))].slice(0, 100)
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
export const cleanColumns = (value, defaults = defaultDevelopmentColumns) => {
  const oldDefault = ['platform_name', 'greeting_no', 'full_name', 'language_names', 'owner_name', 'account_name', 'wechat_status', 'enterprise_status']
  if (!Array.isArray(value)) return [...defaults]
  // 升级已知的旧默认组合；自定义选择（包括全部隐藏）继续保留。
  const previousDefaults = [oldDefault, [...oldDefault, ...(defaults.includes('work_date') ? ['work_date'] : [])]]
  for (const base of [defaults, defaults.filter(key => !['wechat', 'xiaohongshu'].includes(key))]) {
    for (const removed of [[], ['group_large_status'], ['friend_accounts_text'], ['group_large_status', 'friend_accounts_text']]) {
      previousDefaults.push(base.filter(key => !removed.includes(key)))
    }
  }
  if (previousDefaults.some(columns => JSON.stringify(value) === JSON.stringify(columns))) return [...defaults]
  value = value.map(key => key === 'follow_up' ? 'latest_follow_up' : key)
  return developmentColumns.filter(c => value.includes(c.key)).map(c => c.key)
}

export const followUpTime = value => {
  if (!value) return '-'
  const parts = Object.fromEntries(new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(value)).map(part => [part.type, part.value]))
  return `${parts.year}年${parts.month}月${parts.day}日 ${parts.hour}:${parts.minute}:${parts.second}`
}
const followUpSummary = value => {
  const text = (value || '').replace(/\s+/g, ' ').trim()
  return text.length > 100 ? `${text.slice(0, 100)}…` : text
}
export const followUpText = row => row.latest_follow_up_entry
  ? `${followUpSummary(row.latest_follow_up_entry.content)} · ${row.latest_follow_up_entry.operator_name} · ${followUpTime(row.latest_follow_up_entry.created_at)}`
  : followUpSummary(row.latest_follow_up || row.follow_up)

export const developmentDateShortcuts = [
  { key: 'yesterday', label: '昨日', hint: '昨天' },
  { key: 'week', label: '本周', hint: '本周一至今天' },
  { key: 'lastWeek', label: '过去一周', hint: '含今天，最近7天' },
  { key: 'month', label: '本月', hint: '本月1日至今天' },
  { key: 'lastMonth', label: '过去一月', hint: '含今天，最近30天' },
]
// 先取得香港业务日期，再用 UTC 做纯日期运算，避免浏览器时区与夏令时影响边界。
export const developmentDateRange = (key, now = new Date()) => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now).map(p => [p.type, p.value]))
  const end = `${parts.year}-${parts.month}-${parts.day}`
  const start = new Date(`${end}T00:00:00Z`)
  if (key === 'yesterday') start.setUTCDate(start.getUTCDate() - 1)
  else if (key === 'week') start.setUTCDate(start.getUTCDate() - (start.getUTCDay() + 6) % 7)
  else if (key === 'lastWeek') start.setUTCDate(start.getUTCDate() - 6)
  else if (key === 'month') start.setUTCDate(1)
  else if (key === 'lastMonth') start.setUTCDate(start.getUTCDate() - 29)
  else throw new RangeError('未知日期快捷筛选')
  const first = start.toISOString().slice(0, 10)
  return [first, key === 'yesterday' ? first : end]
}
export const statusOptions = ['未处理', '搜不到', '一次请求', '一次请求未通过', '二次请求', '二次请求未通过', '三次请求', '三次请求未通过', '已添加', '（对方）已删']
// 两个渠道分别写历史，成功状态继续共用同一人才入库保护。
export const friendFollowUpOptions = [
  { label: '搜不到微信（不存在）', channels: ['wechat'], status: '搜不到' },
  { label: '搜不到企微（不存在）', channels: ['enterprise'], status: '搜不到' },
  { label: '已添加微信', channels: ['wechat'], status: '已添加' },
  { label: '已添加企微', channels: ['enterprise'], status: '已添加' },
  { label: '已添加微信和企微', channels: ['wechat', 'enterprise'], status: '已添加' },
  ...['一次请求', '一次请求未通过', '二次请求', '二次请求未通过', '三次请求', '三次请求未通过', '（对方）已删'].flatMap(status => ['wechat', 'enterprise'].map(channel => ({ label: `${progressChannels[channel]}：${status}`, channels: [channel], status }))),
]
export const sameDayRange = (today = new Date()) => [dateText(today), dateText(today)]
export const categoryOptions = [{ value: 'national', label: '全国性平台' }, { value: 'local', label: '地方性平台' }, { value: 'international', label: '国外平台' }]

export const defaultProgressStatus = channel => ['wechat', 'enterprise'].includes(channel) ? '已添加' : isGroupChannel(channel) ? '未处理' : progressStatuses(channel).at(-1)
// 与后端保持相同的渠道、成功状态和变更判断；历史原标记不参与自动入库。
export const hasNewPrivateEntry = (actions, previous = []) => {
  const statuses = { wechat: '已添加', enterprise: '已添加', group: '已进群', group_large: '已进群' }
  const old = new Map(previous.map(a => [a.id, a]))
  const latest = new Map(actions.map(a => [a.channel, a.status]))
  return actions.some(a => statuses[a.channel] === a.status && latest.get(a.channel) === a.status &&
    (!old.has(a.id) || old.get(a.id).channel !== a.channel || old.get(a.id).status !== a.status))
}
