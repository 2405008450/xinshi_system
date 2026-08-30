export const emptyFilterValue = (definition) => {
  if (definition.type === 'select') return definition.multiple === false ? '' : []
  if (definition.type === 'date-range' || definition.type === 'number-range') return []
  if (definition.type === 'boolean') return null
  return ''
}

export const isActiveFilterValue = (definition, value) => {
  if (Array.isArray(value)) return value.some((item) => item !== null && item !== undefined && item !== '')
  if (definition.type === 'boolean') return value !== null && value !== undefined && value !== ''
  return String(value ?? '').trim() !== ''
}

export const createFilterModel = (definitions) => Object.fromEntries(
  definitions.map((definition) => [definition.key, emptyFilterValue(definition)])
)

export const resetFilterModel = (model, definitions) => {
  definitions.forEach((definition) => { model[definition.key] = emptyFilterValue(definition) })
}

export const countActiveFilters = (model, definitions) => definitions.reduce(
  (count, definition) => count + (isActiveFilterValue(definition, model[definition.key]) ? 1 : 0),
  0
)

export const buildFieldFilters = (model, definitions) => {
  const result = {}
  definitions.forEach((definition) => {
    const value = model[definition.key]
    if (!isActiveFilterValue(definition, value)) return
    const apiKey = definition.apiKey || definition.key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
    if (definition.type === 'text') result[apiKey] = { op: 'contains', value: String(value).trim() }
    else if (definition.type === 'date-range') result[apiKey] = { op: 'between', from: value?.[0] || null, to: value?.[1] || null }
    else if (definition.type === 'number-range') result[apiKey] = { op: 'between', min: value?.[0] ?? null, max: value?.[1] ?? null }
    else if (definition.type === 'boolean') result[apiKey] = { op: 'eq', value }
    else {
      const values = Array.isArray(value) ? value : [value]
      result[apiKey] = { op: 'in', value: values }
    }
  })
  return result
}

export const serializeFieldFilters = (model, definitions) => {
  const filters = buildFieldFilters(model, definitions)
  return Object.keys(filters).length ? JSON.stringify(filters) : undefined
}
