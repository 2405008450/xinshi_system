const pad = value => String(value).padStart(2, '0')

function parseDateTime(value) {
  if (value instanceof Date) return value
  const normalized = typeof value === 'string' && /^\d{4}-\d{2}-\d{2} /.test(value)
    ? value.replace(' ', 'T')
    : value
  return new Date(normalized)
}

/**
 * 业务界面统一日期时间格式：精确到分钟，不展示秒。
 * 接口传值格式不应使用此方法转换。
 */
export function formatDateTimeMinute(value, emptyText = '-') {
  if (value === null || value === undefined || value === '') return emptyText
  const date = parseDateTime(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 业务界面统一时间格式：时:分。 */
export function formatTimeMinute(value, emptyText = '-') {
  if (value === null || value === undefined || value === '') return emptyText
  const date = parseDateTime(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 仅含时分秒的接口值（如 08:30:00）在界面上统一隐藏秒。 */
export function formatClockMinute(value, emptyText = '-') {
  if (value === null || value === undefined || value === '') return emptyText
  const matched = String(value).match(/^(\d{1,2}):(\d{2})(?::\d{2})?$/)
  return matched ? `${pad(matched[1])}:${matched[2]}` : String(value)
}
