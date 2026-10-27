import { businessDateTimeInputValue } from './dateTime.js'

export const mentionSortOptions = [
  { value: 'time_desc', label: '提及时间：最新在前' },
  { value: 'time_asc', label: '提及时间：最早在前' },
  { value: 'customer_asc', label: '客户：升序' },
  { value: 'customer_desc', label: '客户：倒序' },
]

export function latestMentionAt(session) {
  return (session.variants || [session]).reduce((latest, row) =>
    mentionStamp(row.latestMentionAt) > mentionStamp(latest) ? row.latestMentionAt : latest, null)
}
function mentionStamp(value) {
  if (!value) return 0
  const normalized = businessDateTimeInputValue(value)
  return normalized ? Date.parse(normalized.replace(' ', 'T') + '+08:00') : 0
}
export function compareMentionSessions(a, b, sort = 'time_desc') {
  const unread = Number(Number(b.mentionUnread) > 0) - Number(Number(a.mentionUnread) > 0)
  if (unread) return unread
  if (sort.startsWith('customer_')) {
    const left = a.customerName || '', right = b.customerName || ''
    const missing = Number(!left) - Number(!right)
    if (missing) return missing
    const customer = left.localeCompare(right, 'zh-CN', { numeric: true, sensitivity: 'base' })
    if (customer) return sort === 'customer_desc' ? -customer : customer
  }
  const time = mentionStamp(latestMentionAt(a)) - mentionStamp(latestMentionAt(b))
  return (sort === 'time_asc' ? time : -time) || String(a.key).localeCompare(String(b.key))
}
