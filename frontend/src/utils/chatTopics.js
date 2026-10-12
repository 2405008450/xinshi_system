export function orderedTopicRoots(items, context) {
  const preferred = context === 'annotation' ? 'annotation' : context === 'resource' ? 'resource-development' : ''
  return items.filter(row => !row.parent_id && row.active).sort((a, b) =>
    Number(b.builtin_key === preferred) - Number(a.builtin_key === preferred) || a.sort_order - b.sort_order || a.name.localeCompare(b.name, 'zh-CN'))
}

export function topicSearchParams({ topicId, scope, projectId, projectType, keyword, before }) {
  return { topic_id: topicId, scope, conversation_id: scope === 'current' ? projectId : undefined,
    conversation_type: scope === 'current' ? projectType : undefined, keyword: keyword.trim() || undefined,
    before: before || undefined, limit: 30 }
}

export function messageTopicPatch(data) {
  return { topicId: data.topic_id, topicPath: data.topic_path, topicRevision: data.topic_revision, canClassify: data.can_classify }
}

export function newChatRequestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
