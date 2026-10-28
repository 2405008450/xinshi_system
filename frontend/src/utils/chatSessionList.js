import { businessDateTimeInputValue } from './dateTime.js'

const messageStamp = value => {
  if (!value) return 0
  const normalized = businessDateTimeInputValue(value)
  return normalized ? Date.parse(normalized.replace(' ', 'T') + '+08:00') : 0
}

export function latestSessionMessageAt(session) {
  return (session.variants || [session]).reduce((latest, row) =>
    messageStamp(row.lastMessage?.createdAt) > messageStamp(latest) ? row.lastMessage.createdAt : latest, null)
}

// 普通会话按所有人的最新消息排列；手动置顶仍有效，提及未读不参与排序。
export function compareSessionActivity(a, b) {
  return Number(!!b.pinned) - Number(!!a.pinned)
    || messageStamp(latestSessionMessageAt(b)) - messageStamp(latestSessionMessageAt(a))
    || String(a.key).localeCompare(String(b.key))
}

// 标注子订单由主订单号追加 .001 生成；按订单系列收拢，不能按同名项目合并。
export function sessionListKey(session) {
  const type = session.projectType || session.kind
  const order = String(session.subtitle || '').trim()
  const match = type === 'annotation' && /^(AP-\d{6}-\d+)(?:\.\d{3}){0,2}$/.exec(order)
  return match ? `annotation-order:${match[1]}` : session.key || `${type}:${session.projectId}`
}

const hasConversation = row => row.opened || row.lastMessage || Number(row.unread) > 0 || Number(row.mentionUnread) > 0

export function mentionUnreadCount(sessions) {
  const counts = new Map()
  for (const row of sessions) {
    const key = row.key || row
    counts.set(key, Math.max(counts.get(key) || 0, Number(row.mentionUnread) || 0))
  }
  return [...counts.values()].reduce((sum, count) => sum + count, 0)
}

export function sessionUnreadSignal(session) {
  const mentions = Math.max(0, Number(session.mentionUnread) || 0)
  return { mentions, ordinary: (Number(session.unread) || 0) > mentions }
}

export function firstUnreadMentionSession(sessions) {
  const first = sessions.find(row => Number(row.mentionUnread) > 0)
  if (!first) return null
  // 合并列表项可能选中主订单，实际未读提及来自子订单，必须打开准确订单。
  const target = (first.variants || [first]).find(row => Number(row.mentionUnread) > 0)
  return target ? { ...target, messageId: target.mentionMessageIds?.[0] || '' } : null
}

export function filterClosedSessions(sessions, closedKeys = []) {
  const closed = new Set(closedKeys.filter(key => !key.startsWith('discussion:')))
  const closedGroups = new Set(sessions.filter(row => closed.has(row.key)).map(sessionListKey))
  // 关闭当前订单后，不能用自动关注的空白关联订单重新填回同名列表项。
  return sessions.filter(row => !closed.has(row.key) && (!closedGroups.has(sessionListKey(row)) || hasConversation(row)))
}

export function groupSessionList(sessions, activeKey) {
  const groups = new Map()
  for (const session of sessions) {
    const key = sessionListKey(session)
    if (!groups.has(key)) groups.set(key, new Map())
    // 目录与临时窗口可能同时包含同一会话，未读数只能统计一次。
    const members = groups.get(key)
    const previous = members.get(session.key)
    members.set(session.key, previous ? { ...session, ...previous, opened: previous.opened || session.opened } : session)
  }
  return Array.from(groups.values(), members => {
    const catalog = Array.from(members.values())
    // 自动关注只表示目录可见，不能据此把整个订单系列当作已发起的聊天。
    const started = catalog.filter(hasConversation)
    // 尚未发起聊天的系列保留一个入口；有主订单时优先使用主订单。
    const fallback = catalog.reduce((first, row) =>
      String(row.subtitle || '').split('.').length < String(first.subtitle || '').split('.').length ? row : first)
    const variants = started.length ? started : [fallback]
    const selected = variants.find(row => row.key === activeKey) || variants.find(row => row.opened) || variants[0]
    return {
      ...selected,
      catalogKeys: catalog.map(row => row.key),
      unread: variants.reduce((sum, row) => sum + (Number(row.unread) || 0), 0),
      mentionUnread: variants.reduce((sum, row) => sum + (Number(row.mentionUnread) || 0), 0),
      variants,
    }
  })
}
