export const annotationRegionLevels = [
  { value: 'city', label: '城市' },
  { value: 'district', label: '区县' },
  { value: 'street', label: '街道' },
]

export const annotationRegionLevelLabel = level => annotationRegionLevels.find(item => item.value === level)?.label || '城市'

export const annotationRegionRows = row => (row.languageItems || []).flatMap(item => (item.regions || [])
  .filter(region => region.city || region.district || region.street)
  .map(region => ({ ...region, language: item.display || item.sourceLanguageLabel || '-' })))

export const annotationRegionSummary = (row, level = 'city') => {
  const regions = annotationRegionRows(row)
  const values = [...new Set(regions.map(region => region[level]?.trim()).filter(Boolean))]
  if (regions.length) return { text: values[0] || `未填写${annotationRegionLevelLabel(level)}`, extra: Math.max(0, values.length - 1), hasData: true, legacy: false }
  const original = [...new Set([row.languageRegion, ...(row.areaLabels || [])].map(value => value?.trim()).filter(Boolean))]
  return { text: original[0] || '-', extra: Math.max(0, original.length - 1), hasData: Boolean(original.length), legacy: Boolean(original.length) }
}

export const annotationRegionStorageKey = (page, user) => `annotation-region-level:${page}:${user || 'anonymous'}`

export const readAnnotationRegionLevel = (storage, key) => {
  try {
    const value = storage.getItem(key)
    if (annotationRegionLevels.some(item => item.value === value)) return value
    if (value !== null) storage.removeItem(key)
  } catch { /* 存储不可用时仍能使用当前页面。 */ }
  return 'city'
}

export const saveAnnotationRegionLevel = (storage, key, value) => {
  try { storage.setItem(key, value) } catch { /* 保留本次页面内的展示选择。 */ }
}
