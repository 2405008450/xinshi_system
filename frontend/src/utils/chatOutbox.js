import { isOptimisticMessage, OPTIMISTIC_PREFIX } from './chatOptimistic.js'

const STORAGE_PREFIX = 'chat_outbox_v1:'
const MAX_ITEMS_PER_SCOPE = 30
const MAX_AGE_MS = 7 * 24 * 3600 * 1000
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504])
const DEFAULT_RETRY_DELAYS = [1500, 3000]

const inFlightClientIds = new Set()
let beforeUnloadBound = false

function handleBeforeUnload(event) {
  if (!inFlightClientIds.size) return
  event.preventDefault()
  event.returnValue = ''
}

function syncBeforeUnloadListener() {
  if (typeof window === 'undefined' || !window.addEventListener) return
  if (inFlightClientIds.size > 0 && !beforeUnloadBound) {
    window.addEventListener('beforeunload', handleBeforeUnload)
    beforeUnloadBound = true
  } else if (inFlightClientIds.size === 0 && beforeUnloadBound) {
    window.removeEventListener('beforeunload', handleBeforeUnload)
    beforeUnloadBound = false
  }
}

export function markOutboxInFlight(clientMessageId) {
  if (!clientMessageId) return
  inFlightClientIds.add(String(clientMessageId))
  syncBeforeUnloadListener()
}

export function unmarkOutboxInFlight(clientMessageId) {
  if (!clientMessageId) return
  inFlightClientIds.delete(String(clientMessageId))
  syncBeforeUnloadListener()
}

export function isOutboxInFlight(clientMessageId) {
  return Boolean(clientMessageId && inFlightClientIds.has(String(clientMessageId)))
}

export function outboxInFlightCount() {
  return inFlightClientIds.size
}

export function outboxStorageKey({ userId = '', projectType = '', projectId = '' }) {
  return `${STORAGE_PREFIX}${userId || 'anon'}:${projectType}:${projectId}`
}

function getStorage(storage) {
  if (storage) return storage
  try {
    return typeof localStorage !== 'undefined' ? localStorage : null
  } catch {
    return null
  }
}

function serializeOutboxItem(item) {
  return {
    id: item.id,
    clientMessageId: item.clientMessageId,
    senderUserId: item.senderUserId,
    senderName: item.senderName || '',
    content: item.content || '',
    reply: item.reply ? { id: item.reply.id, senderName: item.reply.senderName, content: item.reply.content } : null,
    attachments: Array.isArray(item.attachments) ? item.attachments : [],
    mentions: [],
    createdAt: item.createdAt || new Date().toISOString(),
    optimisticStatus: item.optimisticStatus || 'failed',
    optimisticError: item.optimisticError || '',
    optimisticOrder: item.optimisticOrder || 0,
    optimisticPayload: item.optimisticPayload || null,
    updatedAt: Date.now(),
  }
}

export function loadOutboxMessages(scope, { storage, now = Date.now() } = {}) {
  const store = getStorage(storage)
  if (!store || !scope?.projectType || !scope?.projectId) return []
  try {
    const raw = store.getItem(outboxStorageKey(scope))
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    const valid = []
    for (const item of parsed) {
      if (!item || !isOptimisticMessage(item) || !item.clientMessageId || !item.optimisticPayload) continue
      if (item.updatedAt && now - item.updatedAt > MAX_AGE_MS) continue
      const stillInFlight = isOutboxInFlight(item.clientMessageId)
      valid.push({
        ...item,
        id: item.id || `${OPTIMISTIC_PREFIX}${item.clientMessageId}`,
        optimisticStatus: stillInFlight ? 'sending' : 'failed',
        optimisticError: stillInFlight ? '' : (item.optimisticError || '上次发送中断或未确认，请点击重试'),
      })
    }
    if (valid.length !== parsed.length) {
      saveOutboxList(scope, valid, { storage: store })
    }
    return valid
  } catch {
    return []
  }
}

function saveOutboxList(scope, items, { storage } = {}) {
  const store = getStorage(storage)
  if (!store || !scope?.projectType || !scope?.projectId) return
  const key = outboxStorageKey(scope)
  try {
    if (!items.length) {
      store.removeItem(key)
    } else {
      store.setItem(key, JSON.stringify(items.slice(-MAX_ITEMS_PER_SCOPE).map(serializeOutboxItem)))
    }
  } catch {
    /* 存储空间不足或受限时降级为仅内存保留，不阻断发送。 */
  }
}

export function upsertOutboxMessage(scope, message, { storage } = {}) {
  if (!message || !message.clientMessageId || !scope?.projectType || !scope?.projectId) return
  const store = getStorage(storage)
  if (!store) return
  let existing = []
  try {
    const raw = store.getItem(outboxStorageKey(scope))
    const parsed = raw ? JSON.parse(raw) : []
    if (Array.isArray(parsed)) existing = parsed
  } catch {
    existing = []
  }
  const index = existing.findIndex(item => item.id === message.id || item.clientMessageId === message.clientMessageId)
  const serialized = serializeOutboxItem(message)
  if (index >= 0) existing[index] = serialized
  else existing.push(serialized)
  saveOutboxList(scope, existing, { storage: store })
}

export function removeOutboxMessage(scope, idOrClientId, { storage } = {}) {
  if (!idOrClientId || !scope?.projectType || !scope?.projectId) return
  const store = getStorage(storage)
  if (!store) return
  try {
    const raw = store.getItem(outboxStorageKey(scope))
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return
    const target = String(idOrClientId)
    const next = parsed.filter(item => item.id !== target && item.clientMessageId !== target)
    if (next.length !== parsed.length) {
      saveOutboxList(scope, next, { storage: store })
    }
  } catch {
    /* 忽略损坏数据 */
  }
}

export function isRetryableSendError(error) {
  if (!error) return false
  if (error.code === 'ERR_CANCELED') return false
  const status = Number(error.status ?? error.response?.status ?? 0)
  if (!status) return true
  return RETRYABLE_STATUS.has(status)
}

export async function sendWithAutoRetry(task, {
  delays = DEFAULT_RETRY_DELAYS,
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms)),
  shouldRetry = isRetryableSendError,
} = {}) {
  let attempt = 0
  while (true) {
    try {
      return await task(attempt)
    } catch (error) {
      if (attempt >= delays.length || !shouldRetry(error)) {
        throw error
      }
      const waitMs = delays[attempt]
      attempt += 1
      await sleep(waitMs)
    }
  }
}
