import { isChatMentionNotification } from './notificationChannels.js'

export const isPersistentChatNotification = item => isChatMentionNotification(item) || String(item.notification_type).endsWith('_invite')

export function isVisibleConversation(item, state, isVisible, document) {
  if (document.visibilityState !== 'visible' || !document.hasFocus()) return false
  const kind = item.related_project_type || (String(item.notification_type).startsWith('direct_chat') ? 'direct' : 'translation')
  const id = String(item.related_entity_id || item.related_project_id || '')
  return state.windows.some(chat => chat.projectType === kind && String(chat.projectId) === id && isVisible(chat))
}

/** 首次成功查询建立基线；重连只补基线之后的普通消息，历史 @ 仍可恢复。 */
export function createChatNotificationFeed() {
  let initialized = false, boundary = 0
  const seen = new Set()
  return {
    get initialized() { return initialized },
    get boundary() { return boundary },
    remember(id) {
      const key = String(id || '')
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    },
    consume(items) {
      const first = !initialized
      const incoming = []
      for (const item of items.slice().reverse()) {
        const fresh = this.remember(item.id)
        const timestamp = Date.parse(item.created_at) || 0
        if ((isPersistentChatNotification(item) || (!first && timestamp >= boundary)) && fresh) incoming.push(item)
      }
      boundary = Math.max(boundary, ...items.map(item => Date.parse(item.created_at) || 0))
      initialized = true
      return incoming
    },
  }
}
