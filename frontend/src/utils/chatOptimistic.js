let optimisticSeq = 0

export const OPTIMISTIC_PREFIX = 'optimistic:'

export function isOptimisticMessage(message) {
  return Boolean(message && (message.optimisticStatus || String(message.id || '').startsWith(OPTIMISTIC_PREFIX)))
}

export function createOptimisticMessage({
  clientMessageId,
  senderUserId,
  senderName = '',
  content = '',
  reply = null,
  attachments = [],
  payload = null,
}) {
  return {
    id: `${OPTIMISTIC_PREFIX}${clientMessageId}`,
    clientMessageId,
    senderUserId,
    senderName,
    content,
    reply: reply ? { id: reply.id, senderName: reply.senderName, content: reply.content } : null,
    attachments: Array.isArray(attachments) ? attachments : [],
    mentions: [],
    createdAt: new Date().toISOString(),
    optimisticStatus: 'sending',
    optimisticError: '',
    optimisticOrder: ++optimisticSeq,
    optimisticPayload: payload,
  }
}

export function matchesOptimisticClientId(optimistic, incoming) {
  if (!isOptimisticMessage(optimistic) || !incoming) return false
  const incomingClientId = incoming.clientMessageId || incoming.client_message_id
  if (incomingClientId && optimistic.clientMessageId && incomingClientId === optimistic.clientMessageId) {
    return true
  }
  return false
}

export function compareOptimisticLast(a, b, compareReal) {
  const optA = isOptimisticMessage(a)
  const optB = isOptimisticMessage(b)
  if (optA && optB) {
    return (a.optimisticOrder || 0) - (b.optimisticOrder || 0)
  }
  if (optA) return 1
  if (optB) return -1
  return compareReal(a, b)
}

export function mergeWithOptimistic(existingList, incomingRows, { replaceTempId = '', compareReal } = {}) {
  const merged = new Map()
  for (const row of existingList) {
    if (replaceTempId && row.id === replaceTempId) continue
    merged.set(row.id, row)
  }
  for (const row of incomingRows) {
    for (const [key, item] of merged.entries()) {
      if (matchesOptimisticClientId(item, row)) {
        merged.delete(key)
      }
    }
    merged.set(row.id, row)
  }
  return [...merged.values()].sort((a, b) => compareOptimisticLast(a, b, compareReal))
}
