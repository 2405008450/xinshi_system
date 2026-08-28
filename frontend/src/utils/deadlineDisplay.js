const BUSINESS_TIME_ZONE = 'Asia/Hong_Kong'
const BUSINESS_TIME_OFFSET = '+08:00'
export const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

const PROJECT_STATUS_ALIASES = {
  pending: 'pending_confirmation',
  in_progress: 'confirmed',
  completed: 'sent_to_client',
  terminated: 'cancelled',
}

const DELIVERED_PROJECT_STATUSES = new Set([
  'sent_to_client',
  'client_feedback',
  'feedback_sent_to_client',
])

const ENDED_PROJECT_STATUSES = new Set(['cancelled', 'partially_cancelled', 'terminated'])

export function parseBusinessDateTime(value) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : new Date(value.getTime())
  const text = String(value).trim()
  const timezoneSuffixPattern = /(Z|[+-]\d{2}:?\d{2})$/i
  const normalized = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(text) && !timezoneSuffixPattern.test(text)
    ? `${text.replace(' ', 'T')}${BUSINESS_TIME_OFFSET}`
    : text
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function getBusinessDateParts(value) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return { year: Number(values.year), month: Number(values.month), day: Number(values.day) }
}

function toDateKey({ year, month, day }) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function shiftDateKey(parts, days) {
  const shifted = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + days))
  return toDateKey({
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
  })
}

export function formatBusinessDateTime(value) {
  if (!value) return '-'
  const date = parseBusinessDateTime(value)
  return date
    ? new Intl.DateTimeFormat('zh-CN', {
      timeZone: BUSINESS_TIME_ZONE,
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date)
    : String(value)
}

function formatRemainingDuration(milliseconds, rounding = 'ceil') {
  const duration = Math.abs(milliseconds)
  const roundValue = rounding === 'floor' ? Math.floor : Math.ceil
  if (duration < HOUR_MS) return `${Math.max(1, roundValue(duration / MINUTE_MS))} 分钟`
  if (duration < DAY_MS) return `${Math.max(1, roundValue(duration / HOUR_MS))} 小时`
  return `${Math.max(1, roundValue(duration / DAY_MS))} 天`
}

function normalizeProjectStatus(status) {
  return PROJECT_STATUS_ALIASES[status] || status
}

function getTerminalHint(status, mode) {
  if (!status) return null
  if (mode === 'task') {
    if (status === 'completed') return { label: '已完成', type: 'success' }
    if (status === 'cancelled') return { label: '已结束', type: 'info' }
    return null
  }
  const normalized = normalizeProjectStatus(status)
  if (DELIVERED_PROJECT_STATUSES.has(normalized)) return { label: '已交付', type: 'success' }
  if (ENDED_PROJECT_STATUSES.has(normalized)) return { label: '已结束', type: 'info' }
  return null
}

export function getDeadlineHint({ deadline, status = '', mode = 'project', now = Date.now() } = {}) {
  const parsed = parseBusinessDateTime(deadline)
  if (!parsed) return { label: '', type: 'info' }

  const terminal = getTerminalHint(status, mode)
  if (terminal) return terminal

  const difference = parsed.getTime() - now
  if (Math.abs(difference) < MINUTE_MS) return { label: '现在截止', type: 'warning' }
  if (difference < 0) return { label: `已逾期 ${formatRemainingDuration(difference, 'floor')}`, type: 'danger' }

  const todayParts = getBusinessDateParts(now)
  const deadlineParts = getBusinessDateParts(parsed)
  let prefix = ''
  if (todayParts && deadlineParts) {
    const deadlineKey = toDateKey(deadlineParts)
    if (deadlineKey === toDateKey(todayParts)) prefix = '今天截止 · '
    else if (deadlineKey === shiftDateKey(todayParts, 1)) prefix = '明天截止 · '
  }
  return {
    label: `${prefix}剩 ${formatRemainingDuration(difference)}`,
    type: prefix ? 'warning' : 'info',
  }
}
