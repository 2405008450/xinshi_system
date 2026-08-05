export const WORD_COUNT_METRICS = [
  { key: 'words', label: '字数', shortLabel: '字数' },
  { key: 'characters_no_spaces', label: '字符数（不计空格）', shortLabel: '不计空格字符' },
  { key: 'cjk_chars_korean_words', label: '中文字符和朝鲜语单词', shortLabel: '中朝统计' },
  { key: 'foreign_words', label: '外文字数', shortLabel: '外文字数' }
]

export const createEmptyWordCountValues = () => Object.fromEntries(
  WORD_COUNT_METRICS.map(({ key }) => [key, null])
)

export const createEmptyWordCountMatrix = () => ({
  company: createEmptyWordCountValues(),
  customer: createEmptyWordCountValues(),
  translatorEstimate: createEmptyWordCountValues()
})

const hasValue = (value) => value !== null && value !== undefined && value !== ''

export function normalizeWordCountValues(values = {}) {
  const normalized = createEmptyWordCountValues()
  WORD_COUNT_METRICS.forEach(({ key }) => {
    const value = values?.[key]
    normalized[key] = hasValue(value) ? Number(value) : null
  })
  return normalized
}

export function normalizeWordCountMatrix(matrix = {}) {
  return {
    company: normalizeWordCountValues(matrix.company),
    customer: normalizeWordCountValues(matrix.customer),
    translatorEstimate: normalizeWordCountValues(matrix.translatorEstimate || matrix.translator_estimate)
  }
}

export function formatWordCountValues(values = {}, { empty = '未填写' } = {}) {
  const filled = WORD_COUNT_METRICS.filter(({ key }) => hasValue(values?.[key]))
  if (!filled.length) return empty
  const first = filled[0]
  const base = `${first.shortLabel} ${Number(values[first.key]).toLocaleString('zh-CN')}`
  return filled.length === 1 ? base : `${base} · 另有 ${filled.length - 1} 项`
}

export function formatWordCountMatrix(matrix = {}, { empty = '尚未填写' } = {}) {
  const normalized = normalizeWordCountMatrix(matrix)
  const dimensions = [
    ['我司', normalized.company],
    ['客户', normalized.customer],
    ['译员预估', normalized.translatorEstimate]
  ]
  const filled = dimensions.flatMap(([label, values]) =>
    WORD_COUNT_METRICS
      .filter(({ key }) => hasValue(values[key]))
      .map((metric) => ({ label, metric, value: values[metric.key] }))
  )
  if (!filled.length) return empty
  const first = filled[0]
  const base = `${first.label}：${first.metric.shortLabel} ${Number(first.value).toLocaleString('zh-CN')}`
  return filled.length === 1 ? base : `${base} · 另有 ${filled.length - 1} 项`
}

export function countWordCountValues(values = {}) {
  return WORD_COUNT_METRICS.filter(({ key }) => hasValue(values?.[key])).length
}

export function sumWordCountValues(items = []) {
  const totals = createEmptyWordCountValues()
  WORD_COUNT_METRICS.forEach(({ key }) => {
    const values = items.map((item) => item?.[key]).filter(hasValue)
    totals[key] = values.length ? values.reduce((sum, value) => sum + Number(value), 0) : null
  })
  return totals
}
