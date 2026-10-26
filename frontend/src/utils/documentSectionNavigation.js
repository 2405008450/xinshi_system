// 根据当前树计算路径，栏目移动或改名后无需维护额外的标题缓存。
export function sectionPath(tree, id) {
  if (!id || typeof id !== 'string') return []
  for (const root of tree) {
    if (root.id === id) return [root]
    const path = sectionPath(root.children || [], id)
    if (path.length) return [root, ...path]
  }
  return []
}

export const flattenSections = tree => tree.flatMap(node => [node,...flattenSections(node.children || [])])
export const sectionHeight = node => 1 + Math.max(0,...(node.children || []).map(sectionHeight))
export function sectionPlacements(tree,parentId=null) {
  return tree.flatMap((node,index)=>[{id:node.id,parentId,sortOrder:index+1,expectedStructureUpdatedAt:node.structureUpdatedAt},...sectionPlacements(node.children || [],node.id)])
}

export function sectionQuery(query, id, queryKey = 'documentSectionId') {
  const next = { ...query }
  if (id) next[queryKey] = id
  else delete next[queryKey]
  return next
}
