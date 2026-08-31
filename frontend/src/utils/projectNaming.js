const padDatePart = (value) => String(value).padStart(2, '0')

export const formatProjectNameDate = (date = new Date()) =>
  `${String(date.getFullYear()).slice(-2)}${padDatePart(date.getMonth() + 1)}${padDatePart(date.getDate())}`

export const formatProjectNameDeadline = (value) => {
  if (!value) return ''
  // Element Plus 提交的是本地时间字符串，优先直接拆分，避免 Date 带来的时区偏移。
  const matched = String(value).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  if (matched) return `${matched[1]}${matched[2]}${matched[3]}-${matched[4]}:${matched[5]}`

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}${padDatePart(date.getMonth() + 1)}${padDatePart(date.getDate())}-${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}`
}

export const buildAutoProjectName = (
  clientShortName,
  subOrderCount = 0,
  date = new Date(),
  languagePair = '',
  customerDeadlineTime = ''
) => {
  const normalizedClientShortName = String(clientShortName || '').trim()
  if (!normalizedClientShortName) return ''

  const normalizedLanguagePair = String(languagePair || '').trim()
  const deadlineText = formatProjectNameDeadline(customerDeadlineTime)
  const parts = [normalizedClientShortName, formatProjectNameDate(date)]
  if (normalizedLanguagePair) parts.push(normalizedLanguagePair)
  if (deadlineText) parts.push(`${deadlineText}回稿`)
  const baseName = parts.join('-')
  return subOrderCount > 0 ? `${baseName}-${subOrderCount}批` : baseName
}

export const isAutoProjectName = (projectName, clientShortName) => {
  const normalizedProjectName = String(projectName || '').trim()
  const normalizedClientShortName = String(clientShortName || '').trim()
  const prefix = `${normalizedClientShortName}-`
  if (!normalizedClientShortName || !normalizedProjectName.startsWith(prefix)) return false

  const suffix = normalizedProjectName.slice(prefix.length)
  if (/^\d{6}$/.test(suffix)) return true
  if (/^\d{6}-\d+批$/.test(suffix)) return true
  return /^\d{6}-.+-\d{8}-\d{2}:?\d{2}回稿(?:-\d+批)?$/.test(suffix)
}
