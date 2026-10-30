import { matchesSearchFields } from './searchMatching'

export function taskTree(rows, keyword = '') {
  const nodes = new Map(rows.map(row => [row.id, { ...row, children: [] }]))
  const roots = []
  for (const node of nodes.values()) {
    const parent = nodes.get(node.parent_id)
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  const filter = (items, level = 1) => items.flatMap(node => {
    const children = filter(node.children, level + 1)
    const matched = matchesSearchFields([node.task_no, node.name, node.content, node.arranger_name, node.executor_name, node.adjustment, node.notes], keyword)
    return matched || children.length ? [{ ...node, level, children: matched && keyword ? annotate(node.children, level + 1) : children }] : []
  })
  const annotate = (items, level) => items.map(node => ({ ...node, level, children: annotate(node.children, level + 1) }))
  return filter(roots)
}

export function canMoveTask(rows, id, parentId) {
  if (parentId && !rows.some(row => row.id === parentId)) return false
  const parents = new Map(rows.map(row => [row.id, row.id === id ? parentId : row.parent_id]))
  if (!parents.has(id)) parents.set(id, parentId)
  for (const start of parents.keys()) {
    let current = start
    const seen = new Set()
    while (current) {
      if (seen.has(current) || seen.size >= 3) return false
      seen.add(current)
      current = parents.get(current)
    }
  }
  return true
}
