const colors = {
  technical: { accent: '#edb57b', soft: '#fff4e8', ink: '#875526' },
  translation: { accent: '#91b9dd', soft: '#edf5fc', ink: '#315f89' },
  resource: { accent: '#88beb6', soft: '#edf7f4', ink: '#326d63' },
  annotation: { accent: '#88bdb6', soft: '#edf7f5', ink: '#326d63' },
  interpretation: { accent: '#b3a5d3', soft: '#f3effa', ink: '#655285' },
  recruitment: { accent: '#d4bb86', soft: '#faf5e9', ink: '#7a6433' },
  general: { accent: '#b6a3d6', soft: '#f4effb', ink: '#68518d' },
  direct: { accent: '#b2abd0', soft: '#f3f0fa', ink: '#665a86' },
  management: { accent: '#9abedb', soft: '#eef6fc', ink: '#3b6688' },
}

export function chatGroupPalette(session = {}, nodes = []) {
  const title = String(session.title || session.name || '')
  const module = session.projectModule || session.projectType || session.kind || session.ruleKey
  if (module === 'technical' || /技术|开发/.test(title)) return colors.technical
  if (colors[module]) return colors[module]
  if (/全体/.test(title)) return colors.general
  if (/资源|facebook|小红书/i.test(title)) return colors.resource
  if (/标注/.test(title)) return colors.annotation
  if (/笔译/.test(title)) return colors.translation
  if (/口译/.test(title)) return colors.interpretation
  if (/招聘/.test(title)) return colors.recruitment
  let node = nodes.find(row => row.id === session.projectId) || nodes.find(row => session.categoryIds?.includes(row.id))
  const visited = new Set()
  while (node?.parentKey && !visited.has(node.id)) {
    visited.add(node.id)
    const parent = nodes.find(row => row.id === node.parentKey)
    if (!parent) break
    node = parent
  }
  return node ? chatGroupPalette({ name: node.name, ruleKey: node.ruleKey }) : colors.management
}

export function chatGroupStyle(session, nodes) {
  const palette = chatGroupPalette(session, nodes)
  return { '--chat-group-accent': palette.accent, '--chat-group-soft': palette.soft, '--chat-group-ink': palette.ink }
}
