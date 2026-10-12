import { businessDateTimeInputValue } from './dateTime.js'

export const chatAvatarText = name => String(name || '').match(/[\p{L}\p{N}]/u)?.[0]?.toUpperCase() || '聊'
export const chatDayKey = value => businessDateTimeInputValue(value).slice(0, 10)
export const chatClock = value => businessDateTimeInputValue(value).slice(11, 16)

export function chatDateLabel(value, now = new Date(), withWeekday = false) {
  const day = chatDayKey(value), today = chatDayKey(now)
  if (!day) return ''
  if (day === today) return withWeekday ? '今天' : chatClock(value)
  const stamp = Date.parse(`${day}T00:00:00+08:00`)
  if (Date.parse(`${today}T00:00:00+08:00`) - stamp === 86400000) return '昨天'
  const [, month, date] = day.split('-')
  const label = `${day.slice(0, 4) !== today.slice(0, 4) ? `${day.slice(0, 4)}年` : ''}${Number(month)}月${Number(date)}日`
  return withWeekday ? `${label} 星期${'日一二三四五六'[new Date(stamp + 8 * 3600000).getUTCDay()]}` : label
}

export function chatGroupStart(message, previous) {
  if (!previous || message.recalledAt || previous.recalledAt || message.senderUserId !== previous.senderUserId || chatDayKey(message.createdAt) !== chatDayKey(previous.createdAt)) return true
  // 公共工具将历史聊天无时区值按已确认的 UTC+8 语义解析。
  const stamp = value => Date.parse(businessDateTimeInputValue(value).replace(' ', 'T') + '+08:00')
  const gap = stamp(message.createdAt) - stamp(previous.createdAt)
  return !Number.isFinite(gap) || gap < 0 || gap > 5 * 60000
}
