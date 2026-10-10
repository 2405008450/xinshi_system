import { businessDateTimeInputValue } from './dateTime.js'

export const formatLocalDate = (value) => (
  businessDateTimeInputValue(value).slice(0, 10)
)

export const defaultProgressSearchRange = (reference = new Date()) => {
  const businessDate = formatLocalDate(reference)
  const [year, month, day] = businessDate.split('-').map(Number)
  const targetMonth = month - 1 - 3
  const lastDay = new Date(Date.UTC(year, targetMonth + 1, 0)).getUTCDate()
  const start = new Date(Date.UTC(year, targetMonth, Math.min(day, lastDay)))
  return [start.toISOString().slice(0, 10), businessDate]
}

export const isProgressSearchRangeValid = (range, maxDays = 366) => {
  if (!Array.isArray(range) || range.length !== 2 || !range[0] || !range[1]) return false
  const start = Date.parse(`${range[0]}T00:00:00Z`)
  const end = Date.parse(`${range[1]}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) return false
  return Math.floor((end - start) / 86400000) + 1 <= maxDays
}

export const splitKeywordMatches = (content, keyword) => {
  const text = String(content || '')
  const needle = String(keyword || '').trim()
  if (!needle) return [{ text, matched: false }]
  const haystack = text.toLocaleLowerCase()
  const normalizedNeedle = needle.toLocaleLowerCase()
  const segments = []
  let cursor = 0
  let matchedAt = haystack.indexOf(normalizedNeedle, cursor)
  while (matchedAt >= 0) {
    if (matchedAt > cursor) segments.push({ text: text.slice(cursor, matchedAt), matched: false })
    const end = matchedAt + needle.length
    segments.push({ text: text.slice(matchedAt, end), matched: true })
    cursor = end
    matchedAt = haystack.indexOf(normalizedNeedle, cursor)
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), matched: false })
  return segments.length ? segments : [{ text, matched: false }]
}
