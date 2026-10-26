import defaults from '../../../data/chat_session_folders.json'
import { sessionListKey } from './chatSessionList.js'
import { annotationStatusLabels, normalizeAnnotationStatus } from './annotationStatus.js'

export const annotationFolderId = defaults.find(row => row.ruleKey === 'annotation').id
export const resourceFolderId = defaults.find(row => row.ruleKey === 'resource').id
export const resourceDiscussionIds = defaults.filter(row => row.parentKey === resourceFolderId).map(row => row.id)
export function sessionFolderNodes(items = []) {
  const builtins = defaults.filter(row => !row.parentKey).map(row => ({ ...row, builtin: true, active: true, assignable: false }))
  const statuses = Object.entries(annotationStatusLabels).map(([status, name]) => ({
    id: `status:${status}`, name, parentKey: annotationFolderId, ruleKey: `status:${status}`, builtin: true, active: true, assignable: false,
  }))
  const builtinIds = new Set(defaults.map(row => row.id))
  const custom = items.filter(row => !builtinIds.has(row.id) && row.parentKey !== resourceFolderId).map(row => ({ ...row, assignable: true }))
  const all = [...builtins, ...statuses, ...custom]
  const roots = new Set(all.filter(row => row.active && !row.parentKey).map(row => row.id))
  const visible = new Set(roots)
  for (let depth = 0; depth < 2; depth++) for (const row of all) if (row.active && visible.has(row.parentKey)) visible.add(row.id)
  return all.filter(row => row.active && visible.has(row.id))
}

export function sessionMatchesFolder(session, id, nodes) {
  if (!id) return true
  const node = nodes.find(row => row.id === id)
  if (!node) return false
  const type = session.projectType || session.kind
  if (id === resourceFolderId && type === 'discussion') return !session.subtitle || session.subtitle === '资源开拓讨论'
  const matches = row => {
    if (session.categoryIds?.includes(row.id)) return true
    if (row.ruleKey?.startsWith('status:')) return type === 'annotation' && normalizeAnnotationStatus(session.projectStatus) === row.ruleKey.slice(7)
    return ['annotation', 'translation', 'interpretation', 'recruitment'].includes(row.ruleKey) && type === row.ruleKey
  }
  const descendants = new Set([id])
  for (let depth = 0; depth < 2; depth++) for (const row of nodes) if (descendants.has(row.parentKey)) descendants.add(row.id)
  return nodes.some(row => descendants.has(row.id) && matches(row))
}

export function sessionFolderCount(sessions, id, nodes) {
  return new Set(sessions.filter(row => (row.projectType || row.kind) !== 'direct' && sessionMatchesFolder(row, id, nodes)).map(sessionListKey)).size
}

export function sessionFolderMentionUnread(sessions, id, nodes) {
  const counts = new Map()
  for (const row of sessions) {
    if ((row.projectType || row.kind) === 'direct' || !sessionMatchesFolder(row, id, nodes)) continue
    counts.set(row.key, Math.max(counts.get(row.key) || 0, Number(row.mentionUnread) || 0))
  }
  return [...counts.values()].reduce((sum, count) => sum + count, 0)
}

export function assignableSessionFolders(items) {
  const nodes = sessionFolderNodes(items)
  return nodes.filter(row => row.assignable).map(row => ({ ...row,
    label: [nodes.find(parent => parent.id === row.parentKey)?.name, row.name].filter(Boolean).join(' / '),
  }))
}
