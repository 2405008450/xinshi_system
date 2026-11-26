import defaults from '../../../data/chat_session_folders.json'
import companyChatRooms from '../../../data/company_chat_rooms.json'
import { sessionListKey } from './chatSessionList.js'
import { normalizeAnnotationStatus } from './annotationStatus.js'
import { PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType } from './projectStatus.js'

export const annotationFolderId = defaults.find(row => row.ruleKey === 'annotation').id
export const annotationStatusGroupId = 'annotation:statuses'
export const resourceFolderId = defaults.find(row => row.ruleKey === 'resource').id
export const technicalFolderId = defaults.find(row => row.ruleKey === 'technical').id
export const resourceDiscussionIds = defaults.filter(row => row.parentKey === resourceFolderId).map(row => row.id)

const managementNames = {
  annotation: ['标注通用讨论'],
  translation: ['笔译项目管理讨论', '笔译业务'],
  interpretation: ['口译项目管理讨论', '口译项目管理'],
  recruitment: ['招聘项目管理讨论'],
}
const statusRootId = module => module === 'annotation' ? annotationStatusGroupId : `status-root:${module}`

export function annotationFolderEntries(rows, parentId) {
  const module = defaults.find(row => row.id === parentId)?.ruleKey
  if (!managementNames[module]) return rows
  const isManagement = row => row.isConversation && managementNames[module].includes(row.name)
  const isStatus = row => row.id === statusRootId(module)
  return [
    ...rows.filter(isManagement), ...rows.filter(isStatus),
    ...(module === 'annotation' ? [{ id: 'annotation-technical-picker', parentKey: annotationFolderId, isTechnicalEntry: true }] : []),
    ...rows.filter(row => !isManagement(row) && !isStatus(row)),
  ]
}

export function placeCompanyConversations(roots) {
  const priority = [
    ...roots.filter(row => row.isConversation && ['（全体大群）','全体大群'].includes(row.name)),
    ...roots.filter(row => row.name === '内部管理群' && !row.isConversation),
    ...roots.filter(row => row.id === resourceFolderId),
    ...['annotation','translation','interpretation','recruitment','technical'].flatMap(module=>roots.filter(row=>row.ruleKey===module)),
  ]
  const ids=new Set(priority.map(row=>row.id))
  return [...priority,...roots.filter(row=>!ids.has(row.id))]
}
export function sessionFolderNodes(items = [], { technicalAccess = false } = {}) {
  const builtins = defaults.filter(row => !row.parentKey && (row.id !== technicalFolderId || technicalAccess)).map(row => ({ ...row, builtin: true, active: true, assignable: false }))
  const resourceNodes = defaults.filter(row => row.parentKey === resourceFolderId).map(row => ({
    ...row, ...items.find(item=>item.id===row.id), builtin:true, active:items.find(item=>item.id===row.id)?.active ?? true,
    isConversation:true,assignable:false,
  }))
  const statuses = Object.entries(PROJECT_STATUS_OPTIONS).flatMap(([module, options]) => {
    const parent = defaults.find(row => row.ruleKey === module)
    if (!parent) return []
    const statusRoot = statusRootId(module)
    return [{id:statusRoot, name:'项目状态', parentKey:parent.id, ruleKey:'project-status', projectModule:module,
      builtin:true,active:true,assignable:false}, ...[...options,{value:'__unset',label:'未设置状态'}].map(({value, label}) => ({
      id: module === 'annotation' ? `status:${value}` : `status:${module}:${value}`, name:label, parentKey:statusRoot,
      ruleKey:`status:${value}`,projectModule:module,statusIcon:({primary:'Loading',warning:'Clock',danger:'CircleClose',success:'CircleCheck'})[getProjectStatusType(module,value)] || 'Document',
      builtin:true,active:true,assignable:false,
    }))]
  })
  const builtinIds = new Set(defaults.map(row => row.id))
  const custom = items.filter(row => !(!row.parentKey && ['通用标注','通用标注会话'].includes(row.name)) && !builtinIds.has(row.id) && (technicalAccess || row.name !== '技术/开发沟通')).map(row => ({ ...row, assignable: !row.builtin && row.assignable !== false }))
  const all = [...builtins, ...resourceNodes, ...statuses, ...custom].map(row=>row.isConversation && row.parentKey===resourceFolderId ? {...row,conversationIcon: /facebook|小红书/i.test(row.name)?'Promotion':({'平台讨论':'Grid','资源讨论':'UserFilled','企微管理':'ChatDotRound','发布需求':'Promotion','高校渠道':'School','其他渠道':'MoreFilled'})[row.name] || 'ChatDotRound'} : row)
  const roots = new Set(all.filter(row => row.active && !row.parentKey).map(row => row.id))
  const visible = new Set(roots)
  for (let depth = 0; depth < 3; depth++) for (const row of all) if (row.active && visible.has(row.parentKey)) visible.add(row.id)
  return all.filter(row => row.active && visible.has(row.id))
}

export function sessionMatchesFolder(session, id, nodes) {
  if (!id) return true
  const node = nodes.find(row => row.id === id)
  if (!node) return false
  const type = session.projectType || session.kind
  if (id === resourceFolderId && type === 'discussion' && ['资源开拓讨论','资源开拓与讨论'].includes(session.subtitle)) return true
  const matches = row => {
    if (row.isConversation && type === 'discussion' && String(session.projectId) === row.id) return true
    if (session.categoryIds?.includes(row.id)) return true
    const module = session.projectModule || type
    if (row.ruleKey === 'project-status') return module === row.projectModule
    if (row.ruleKey?.startsWith('status:')) return module === row.projectModule && (normalizeProjectStatus(module, module === 'annotation' ? normalizeAnnotationStatus(session.projectStatus) : session.projectStatus) || '__unset') === row.ruleKey.slice(7)
    return ['annotation', 'translation', 'interpretation', 'recruitment'].includes(row.ruleKey) && type === row.ruleKey
  }
  const descendants = new Set([id])
  for (let depth = 0; depth < 3; depth++) for (const row of nodes) if (descendants.has(row.parentKey)) descendants.add(row.id)
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

export function assignableSessionFolders(items, options) {
  const nodes = sessionFolderNodes(items, options)
  return nodes.filter(row => row.assignable).map(row => ({ ...row,
    label: [nodes.find(parent => parent.id === row.parentKey)?.name, row.name].filter(Boolean).join(' / '),
  }))
}
