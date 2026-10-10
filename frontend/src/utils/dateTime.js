const pad = value => String(value).padStart(2, '0')

const businessDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
})

/** 文档编辑时间按 UTC+8 展示；历史无时区值按业务本地时间解析。 */
export function formatBusinessDateTime(value) {
  if (value === null || value === undefined || value === '') return '-'
  let normalized = value
  if (typeof value === 'string') {
    normalized = value.trim().replace(/^(\d{4}-\d{2}-\d{2}) /, '$1T')
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(normalized)) {
      normalized += '+08:00'
    }
  }
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? '-' : businessDateTimeFormatter.format(date)
}

/** 表单、进度和业务日期固定使用香港时间，不依赖浏览器时区。 */
export function businessDateTimeInputValue(value = new Date()) {
  if (value === null || value === '') return ''
  let normalized = value
  if (typeof value === 'string') {
    normalized = value.trim().replace(' ', 'T')
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(normalized)) normalized += '+08:00'
  }
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return ''
  const shifted = new Date(date.getTime() + 8 * 3600000)
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())}`
}

export function formatBusinessDateTimeMinute(value, emptyText = '-') {
  if (value === null || value === undefined || value === '') return emptyText
  const formatted = businessDateTimeInputValue(value)
  return formatted ? formatted.slice(0, 16).replace(/^(\d{4})-(\d{2})-(\d{2}) /, '$1年$2月$3日 ') : emptyText
}

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
