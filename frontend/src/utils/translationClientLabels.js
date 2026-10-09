const clientFieldKeys = new Set([
  'clientName', 'clientShortName', 'clientCode', 'clientManager', 'managerContact',
])

export function getTranslationClientDetailItems(items, row) {
  if (!String(row?.subClientShortName || '').trim()) return items
  return items.map((item) => clientFieldKeys.has(item.key)
    ? { ...item, label: `母${item.label}` }
    : item)
}
