const PREFIX = 'xinshi.notification.acknowledged:'
const EVENT = 'xinshi-notification-acknowledged'

// 每条通知独立存储，避免多个标签页同时操作时覆盖彼此的确认结果。
export function createNotificationAcknowledgements({
  storage = () => globalThis.localStorage,
  target = globalThis.window,
  userId = () => storage()?.getItem('user_id'),
} = {}) {
  const memory = new Set()
  const currentUser = () => { try { return userId() } catch { return null } }
  const keyFor = (id, actor = currentUser()) => actor && id != null && String(id)
    ? `${PREFIX}${encodeURIComponent(actor)}:${encodeURIComponent(id)}` : ''
  function has(id) {
    const key = keyFor(id)
    if (!key) return false
    try { return memory.has(key) || storage()?.getItem(key) === '1' }
    catch { return memory.has(key) }
  }
  function acknowledge(id) {
    const actor = currentUser(), key = keyFor(id, actor)
    if (!key || has(id)) return
    memory.add(key)
    try { storage()?.setItem(key, '1') } catch { /* 存储受限时，本标签页仍保持确认结果。 */ }
    target?.dispatchEvent(new CustomEvent(EVENT, { detail: { actor, id: String(id) } }))
  }
  function subscribe(handler) {
    const local = event => {
      if (event.detail?.actor === currentUser()) handler(event.detail.id)
    }
    const remote = event => {
      if (event.storageArea && event.storageArea !== storage()) return
      const actor = currentUser(), prefix = actor ? `${PREFIX}${encodeURIComponent(actor)}:` : ''
      if (!prefix || event.newValue !== '1' || !event.key?.startsWith(prefix)) return
      try {
        const id = decodeURIComponent(event.key.slice(prefix.length))
        memory.add(event.key); handler(id)
      } catch { /* 忽略不完整的存储事件。 */ }
    }
    target?.addEventListener(EVENT, local)
    target?.addEventListener('storage', remote)
    return () => {
      target?.removeEventListener(EVENT, local)
      target?.removeEventListener('storage', remote)
    }
  }
  function rememberRead(items, actor = currentUser()) {
    // 请求完成前可能已退出或切换账号，不能把旧响应记到新账号。
    if (!actor || actor !== currentUser()) return
    for (const item of items || []) if (item?.is_read === true) acknowledge(item.id)
  }
  return { has, acknowledge, subscribe, rememberRead, actor: currentUser }
}

export const notificationAcknowledgements = createNotificationAcknowledgements()
