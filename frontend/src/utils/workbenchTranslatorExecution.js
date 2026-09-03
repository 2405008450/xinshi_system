import { parseBusinessDateTime } from './deadlineDisplay.js'

export function getWorkbenchTaskKey(row) {
  return `${row?.source_kind || row?.source_type || 'project'}:${row?.source_id || row?.workflow_instance_id || row?.project_responsibility_id || row?.order_no}`
}

export function hasTranslatorExecutionItems(row) {
  const items = row?.translator_execution?.items
  return Array.isArray(items) && items.some(item => item.needs_attention || item.assigned_translators?.length)
}

export function filterTranslatorExecutionItems(row, showAll = false) {
  const items = Array.isArray(row?.translator_execution?.items) ? row.translator_execution.items : []
  if (showAll || !row?.translator_execution?.attention_count) return items
  return items.filter(item => item.needs_attention)
}

export function getAttentionTranslatorEntries(row) {
  const entries = []
  for (const item of row?.translator_execution?.items || []) {
    if (!item.needs_attention) continue
    if (!item.assigned_translators?.length) {
      entries.push({ translatorName: item.sub_project_name || item.order_no, time: null })
      continue
    }
    for (const translator of item.assigned_translators) {
      entries.push({
        translatorName: translator.translator_name || '译员',
        time: translator.translator_return_time || null,
      })
    }
  }
  return entries.sort((left, right) => {
    const leftTime = parseBusinessDateTime(left.time)?.getTime() ?? Number.POSITIVE_INFINITY
    const rightTime = parseBusinessDateTime(right.time)?.getTime() ?? Number.POSITIVE_INFINITY
    return leftTime - rightTime
  })
}

export function getTranslatorCompletionSummaries(row) {
  const values = []
  for (const item of row?.translator_execution?.items || []) {
    for (const translator of item.assigned_translators || []) {
      const remarks = String(translator.completion_remarks || '').trim()
      if (remarks) values.push(`${item.order_no} · ${translator.translator_name}：${remarks}`)
    }
  }
  return values
}

export function getTranslatorExecutionRiskRank(row, now = new Date()) {
  const execution = row?.translator_execution
  if (!execution?.attention_count) return 3
  if (execution.overdue_count) return 0
  const nextReturn = parseBusinessDateTime(execution.next_return_time)
  if (!nextReturn) return 2
  return nextReturn.getTime() <= now.getTime() + 24 * 60 * 60 * 1000 ? 1 : 2
}

export function reconcileTranslatorExpandedKeys(rows, expandedKeys, manuallyCollapsedKeys) {
  const visibleKeys = new Set(rows.map(getWorkbenchTaskKey))
  const next = new Set(expandedKeys.filter(key => visibleKeys.has(key)))
  rows.forEach((row) => {
    const key = getWorkbenchTaskKey(row)
    if (row?.translator_execution?.attention_count && !manuallyCollapsedKeys.has(key)) next.add(key)
  })
  return [...next]
}

export function getWorkbenchExecutionDefaultColumnKeys(columns, isProjectAssistant) {
  return columns
    .filter(column => isProjectAssistant || !['translatorReturn', 'taskCompletion'].includes(column.key))
    .map(column => column.key)
}
