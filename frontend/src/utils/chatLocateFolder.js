import { normalizeAnnotationStatus } from './annotationStatus.js'
import { normalizeProjectStatus } from './projectStatus.js'

function nodeDepth(node, byId) {
  let depth = 0
  let cur = node
  const seen = new Set()
  while (cur?.parentKey && !seen.has(cur.id)) {
    seen.add(cur.id)
    const parent = byId.get(cur.parentKey)
    if (!parent) break
    cur = parent
    depth += 1
  }
  return depth
}

/**
 * 为「快速定位到会话分组」计算会话在分组树中的最深归属节点 ID：
 * - 私聊不属于会话分组，返回 ''；
 * - 讨论会话优先匹配自身会话节点，其次匹配最深分类节点或资源开拓分组；
 * - 业务项目优先匹配最深自定义分类，其次匹配精准项目状态叶子节点，最后回退到模块一级分组。
 */
export function locateConversationFolder(session, nodes = []) {
  if (!session || !Array.isArray(nodes) || !nodes.length) return ''
  const type = session.projectType || session.kind
  if (!type || type === 'direct') return ''

  const byId = new Map(nodes.map(row => [row.id, row]))
  const resourceNode = nodes.find(row => !row.parentKey && row.ruleKey === 'resource')
  const resourceId = resourceNode?.id || ''
  const resourceChildIds = resourceId
    ? nodes.filter(row => row.parentKey === resourceId).map(row => row.id)
    : []
  const pid = session.projectId != null ? String(session.projectId) : ''

  if (type === 'discussion') {
    const own = nodes.find(row => row.isConversation && row.id === pid)
    if (own) return own.id
    const categoryIds = Array.isArray(session.categoryIds) ? session.categoryIds : []
    const matchedCategories = categoryIds
      .map(id => byId.get(id))
      .filter(Boolean)
      .sort((a, b) => nodeDepth(b, byId) - nodeDepth(a, byId))
    if (matchedCategories.length) return matchedCategories[0].id
    if (resourceId && (['资源开拓讨论', '资源开拓与讨论'].includes(session.subtitle) || resourceChildIds.includes(pid))) {
      return resourceId
    }
    return ''
  }

  const categoryIds = Array.isArray(session.categoryIds) ? session.categoryIds : []
  const customCategories = categoryIds
    .map(id => byId.get(id))
    .filter(row => row && row.id !== resourceId && !row.builtin)
    .sort((a, b) => nodeDepth(b, byId) - nodeDepth(a, byId))
  if (customCategories.length) return customCategories[0].id

  const module = session.projectModule || type
  const rawStatus = module === 'annotation'
    ? normalizeAnnotationStatus(session.projectStatus)
    : session.projectStatus
  const normalizedStatus = normalizeProjectStatus(module, rawStatus) || '__unset'
  const statusNode = nodes.find(
    row => row.projectModule === module && row.ruleKey === `status:${normalizedStatus}`,
  )
  if (statusNode) return statusNode.id

  const moduleRoot = nodes.find(row => !row.parentKey && row.ruleKey === module)
  return moduleRoot?.id || ''
}
