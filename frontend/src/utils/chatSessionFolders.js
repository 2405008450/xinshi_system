import defaults from '../../../data/chat_session_folders.json'
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
  return all.filter(row => row.active && (!row.parentKey || roots.has(row.parentKey)))
}

export function sessionMatchesFolder(session, id, nodes) {
  if (!id) return true
  const node = nodes.find(row => row.id === id)
  if (!node) return false
  const type = session.projectType || session.kind
  if (id === resourceFolderId && type === 'discussion') return true
  const matches = row => {
    if (session.categoryIds?.includes(row.id)) return true
    if (row.ruleKey?.startsWith('status:')) return type === 'annotation' && normalizeAnnotationStatus(session.projectStatus) === row.ruleKey.slice(7)
    return ['annotation', 'translation', 'interpretation', 'recruitment'].includes(row.ruleKey) && type === row.ruleKey
  }
  return matches(node) || nodes.some(row => row.parentKey === id && matches(row))
}

export function sessionFolderCount(sessions, id, nodes) {
  return new Set(sessions.filter(row => (row.projectType || row.kind) !== 'direct' && sessionMatchesFolder(row, id, nodes)).map(row => row.key || `${row.projectType || row.kind}:${row.projectId}`)).size
}

export function assignableSessionFolders(items) {
  const nodes = sessionFolderNodes(items)
  return nodes.filter(row => row.assignable).map(row => ({ ...row,
    label: [nodes.find(parent => parent.id === row.parentKey)?.name, row.name].filter(Boolean).join(' / '),
  }))
}
