export function annotationChildName(parentName, sourceLabel, targetLabel = '') {
  const name = (parentName || '').trim()
  const source = (sourceLabel || '').trim()
  const target = (targetLabel || '').trim()
  if (!name || !source) return name
  return `${source}${target ? `→${target}` : ''}-${name}`
}
