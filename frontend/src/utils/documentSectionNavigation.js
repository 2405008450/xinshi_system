// 根据当前树计算路径，栏目移动或改名后无需维护额外的标题缓存。
export function sectionPath(tree, id) {
  if (!id || typeof id !== 'string') return []
  for (const root of tree) {
    if (root.id === id) return [root]
    const child = (root.children || []).find(item => item.id === id)
    if (child) return [root, child]
  }
  return []
}

export function sectionQuery(query, id, queryKey = 'documentSectionId') {
  const next = { ...query }
  if (id) next[queryKey] = id
  else delete next[queryKey]
  return next
}
