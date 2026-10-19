import { formatBusinessDateTime } from './dateTime.js'
import { categoryOptions } from './resourceDevelopment.js'

export const arrangementDefinitions = options => Array.isArray(options.arrangement_platforms)
  ? options.arrangement_platforms
  : (options.options || []).filter(item => item.kind === 'platform')

// 同一层级函数供列表、编辑及详情复用；只按 ID 关联，不从账号名称推断品牌。
export function groupArrangementAccounts(options, cells = [], { includeUnarranged = true, includeEmpty = true, includePlaceholders = false } = {}) {
  const definitions = new Map(arrangementDefinitions(options).map(item => [item.id, item]))
  const existing = new Map(cells.map((cell, index) => [cell.platform_id, { cell, index }]))
  const ids = new Set(existing.keys())
  if (includeUnarranged) for (const item of definitions.values()) {
    if ((item.kind === 'platform' || (includePlaceholders && item.kind === 'channel_group')) && !item.has_accounts) ids.add(item.id)
  }
  const groups = new Map(categoryOptions.map(item => [item.value, { ...item, platforms: new Map() }]))
  for (const id of ids) {
    const definition = definitions.get(id)
    const { cell = null, index = -1 } = existing.get(id) || {}
    const category = groups.has(definition?.category) ? definition.category : 'unknown'
    if (!groups.has(category)) groups.set(category, { value: category, label: '待分类', platforms: new Map() })
    const group = groups.get(category)
    const platformId = definition?.parent_id || id
    const name = cell?.platform_name || definition?.name || '-'
    const platformName = definition?.parent_name || definition?.name || name
    const placeholder = definition?.kind === 'channel_group' && !cell
    if (!group.platforms.has(platformId)) group.platforms.set(platformId, { id: platformId, name: platformName, accounts: [] })
    group.platforms.get(platformId).accounts.push({
      id, name, placeholder, accountName: placeholder ? '暂无账号' : definition?.parent_id ? name : '单账号',
      category, categoryLabel: group.label, platformId, platformName,
      description: definition?.description || '', cell, index,
      path: `${group.label} / ${platformName}${placeholder ? ' / 暂无账号' : definition?.parent_id ? ` / ${name}` : ' / 单账号'}`,
    })
  }
  const compare = (a, b) => a.name.localeCompare(b.name, 'zh-CN', { numeric: true }) || a.id.localeCompare(b.id)
  return [...groups.values()].map(group => ({ ...group,
    platforms: [...group.platforms.values()].sort(compare).map(platform => ({ ...platform, accounts: platform.accounts.sort(compare) })),
  })).filter(group => includeEmpty || group.platforms.length)
}

export function arrangementTableRows(groups) {
  return groups.flatMap(group => {
    const rows = group.platforms.flatMap(platform => platform.accounts.map((account, index) => ({
      ...account, platformSpan: index === 0 ? platform.accounts.length : 0, categorySpan: 0,
    })))
    if (!rows.length) rows.push({ id: `empty:${group.value}`, category: group.value, categoryLabel: group.label, empty: true, platformSpan: 1 })
    rows[0].categorySpan = rows.length
    return rows
  })
}

export const arrangementTableSpan = ({ row, columnIndex }) => {
  if (columnIndex === 0) return [row.categorySpan, row.categorySpan ? 1 : 0]
  if (row.empty) return columnIndex === 1 ? [1, 7] : [0, 0]
  if (columnIndex === 1) return [row.platformSpan, row.platformSpan ? 1 : 0]
  return [1, 1]
}

export const arrangementTargetKey = target => [target.kind, target.request_id || '', target.language_id || ''].join(':')
export function arrangementTargetLabel(target) {
  const project = target.project?.project_name?.trim() || target.source_name?.trim() || ''
  const label = target.label?.trim() || ''
  const parts = target.kind === 'request_project' ? [project || label || '未命名需求'] : [...new Set([label, project].filter(Boolean))]
  return `${parts.join(' · ') || '未命名方向'}${target.active === false ? `（${target.inactive_reason || '已失效'}）` : ''}`
}
export const arrangementProjectKey = project => `${project.source_type}:${project.project_id}`
// 只展示本次安排快照中的范围，不将整个项目的城市与语种交叉拼接。
export function arrangementProjectScopes(targets = []) {
  return [...new Set(targets.flatMap(target => target.kind === 'request_project' && target.scope_recorded === false
    ? ['语种、城市范围未记录'] : target.scope?.length
    ? target.scope.map(scope => `${scope.language_label || target.label || '语种未配置'} · ${[scope.city, scope.district, scope.street].filter(Boolean).join(' / ') || '城市未配置'}`)
    : [`${target.kind === 'request_project' ? '语种未配置' : target.label || '语种未配置'} · 城市未配置`]))]
}
export const arrangementPopoverOptions = { modifiers: [
  { name: 'flip', options: { fallbackPlacements: [] } },
  { name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } },
] }
export const arrangementProjectTypes = [
  { value: 'annotation', label: '标注（含子订单）' }, { value: 'translation', label: '笔译' },
  { value: 'interpretation', label: '口译' }, { value: 'recruitment', label: '招聘' },
]
export const arrangementToday = (now = new Date()) => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(now)
// 香港业务日期加一天，使用 UTC 做纯日期运算，避免浏览器时区和夏令时影响。
export const arrangementTomorrow = (now = new Date()) => {
  const date = new Date(`${arrangementToday(now)}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}
export const arrangementChineseDate = value => new Date(`${value}T00:00:00+08:00`).toLocaleDateString('zh-CN', { timeZone:'Asia/Hong_Kong' })
export const arrangementChineseTime = formatBusinessDateTime
export const arrangementCellPayload = cell => ({
  platform_id: cell.platform_id, owner_id: cell.owner_id || null,
  targets: (cell.targets || []).map(t => ({ kind: t.kind, request_id: t.request_id || null, language_id: t.language_id || null,
    ...(t.kind === 'request_project' && t.scope ? { selected_scope_keys: t.scope.map(item => item.key) } : {}),
    ...(t.kind === 'request_project' && t.arrangement_note !== undefined ? { arrangement_note: t.arrangement_note } : {}),
  })),
  role_tags: normalizeArrangementRoles(cell.role_tags),
  projects: (cell.manual_projects || []).map(p => ({ source_type: p.source_type, project_id: p.project_id })),
  remarks: cell.remarks || '',
})
export const normalizeArrangementRoles = tags => [...new Set((tags || []).map(tag => tag.trim()).filter(Boolean))]
export const arrangementCellChanged = (cell, previous) => JSON.stringify(arrangementCellPayload(cell)) !== JSON.stringify(arrangementCellPayload(previous || { platform_id: cell.platform_id }))
export function arrangementProjectRoute(project) {
  const names = { annotation: project.parent_project_id ? 'AnnotationChildOrders' : 'AnnotationProjectDetails',
    translation: 'TranslationProjectDetails', interpretation: 'InterpretationProjectDetails', recruitment: 'RecruitmentProjectDetails' }
  return { name: names[project.source_type], query: { projectId: project.project_id,
    ...(project.parent_project_id ? { parentProjectId: project.parent_project_id } : {}) } }
}
