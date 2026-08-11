export const WORD_COUNT_METRICS = [
  { key: 'words', label: '字数', shortLabel: '字数' },
  { key: 'characters_no_spaces', label: '字符数（不计空格）', shortLabel: '不计空格字符' },
  { key: 'cjk_chars_korean_words', label: '中文字符和朝鲜语单词', shortLabel: '中朝统计' },
  { key: 'foreign_words', label: '外文字数', shortLabel: '外文字数' }
]

const METRIC_KEY_ALIASES = {
  words: ['words'],
  characters_no_spaces: ['characters_no_spaces', 'charactersNoSpaces'],
  cjk_chars_korean_words: ['cjk_chars_korean_words', 'cjkCharsKoreanWords'],
  foreign_words: ['foreign_words', 'foreignWords']
}

export const createEmptyWordCountValues = () => Object.fromEntries(
  WORD_COUNT_METRICS.map(({ key }) => [key, null])
)

export const createEmptyWordCountMatrix = () => ({
  company: createEmptyWordCountValues(),
  customer: createEmptyWordCountValues(),
  translatorEstimate: createEmptyWordCountValues()
})

const hasValue = (value) => value !== null && value !== undefined && value !== ''

function readMetricValue(values = {}, metricKey) {
  const aliases = METRIC_KEY_ALIASES[metricKey] || [metricKey]
  for (const alias of aliases) {
    if (hasValue(values?.[alias])) return values[alias]
  }
  return null
}

export function normalizeWordCountValues(values = {}) {
  const normalized = createEmptyWordCountValues()
  WORD_COUNT_METRICS.forEach(({ key }) => {
    const value = readMetricValue(values, key)
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

function collectFilledWordCountEntries(matrix = {}, translators = []) {
  const normalized = normalizeWordCountMatrix(matrix)
  const dimensions = [
    ['我司', normalized.company],
    ['客户', normalized.customer],
    ['译员预估', normalized.translatorEstimate]
  ]
  const entityEntries = dimensions.flatMap(([label, values]) =>
    WORD_COUNT_METRICS
      .filter(({ key }) => hasValue(values[key]))
      .map((metric) => ({ label, metric, value: values[metric.key] }))
  )
  const translatorEntries = (translators || []).flatMap((translator) => {
    const translatorName = translator.translator_name || translator.translatorName || '当前译员'
    return [
      [`${translatorName} · 预定`, normalizeWordCountValues(translator.planned)],
      [`${translatorName} · 实际`, normalizeWordCountValues(translator.actual)]
    ].flatMap(([label, values]) =>
      WORD_COUNT_METRICS
        .filter(({ key }) => hasValue(values[key]))
        .map((metric) => ({ label, metric, value: values[metric.key] }))
    )
  })
  return [...entityEntries, ...translatorEntries]
}

export function formatWordCountMatrix(matrix = {}, { empty = '尚未填写', translators = [] } = {}) {
  const filled = collectFilledWordCountEntries(matrix, translators)
  if (!filled.length) return empty
  const first = filled[0]
  const base = `${first.label}：${first.metric.shortLabel} ${Number(first.value).toLocaleString('zh-CN')}`
  return filled.length === 1 ? base : `${base} · 另有 ${filled.length - 1} 项`
}

/** 列表单元格按界面行序取首个有效值，仅展示数字。 */
export function getWordCountMatrixListSummary(matrix = {}, { empty = '—', translators = [] } = {}) {
  const filled = collectFilledWordCountEntries(matrix, translators)
  if (!filled.length) {
    return { primary: empty, extraCount: 0, title: '尚未填写' }
  }
  const preferred = filled[0]
  const numberText = Number(preferred.value).toLocaleString('zh-CN')
  return {
    primary: numberText,
    extraCount: Math.max(0, filled.length - 1),
    title: formatWordCountMatrix(matrix, { translators })
  }
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
