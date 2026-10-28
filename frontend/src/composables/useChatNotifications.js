import { nextTick, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getNotifications, markNotificationRead } from '@/api/notifications'
import { chatRequest } from '@/api/projectChat'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { subscribe } from '@/utils/realtimeSocket'
import { showDesktopNotification } from '@/utils/desktopNotifications'
import { isChatNotification, isChatMentionNotification, CONVERSATION_NOTIFICATION_TYPES } from '@/utils/notificationChannels'
import { notificationAcknowledgements } from '@/utils/notificationAcknowledgements'

/** 聊天独立承接留言、提及和群邀请，通知铃铛仅负责业务提醒。 */
export function useChatNotifications() {
  const { openChat, openFullscreen } = useProjectChatDock()
  const isConversationNotice = item => CONVERSATION_NOTIFICATION_TYPES.includes(String(item?.notification_type))
  const seen = new Set(), reading = new Set()
  let timer, controller, loading = false, disposed = false, generation = 0, pendingInitial = false
  const cleanups = []
  const remember = id => {
    if (!id || seen.has(String(id))) return false
    seen.add(String(id))
    while (seen.size > 200) seen.delete(seen.values().next().value)
    return true
  }
  async function activateNotification(item, showError = false) {
    notificationAcknowledgements.acknowledge(item.id)
    const projectType = item.related_project_type || (String(item.notification_type).startsWith('direct_chat') ? 'direct' : 'translation')
    const projectId = item.related_entity_id || item.related_project_id
    if (!projectId) { if (showError) ElMessage.info('关联会话已不可用'); return false }
    let messageId = ''
    if (isChatMentionNotification(item)) {
      try { const target = await chatRequest(`mentions/${item.id}/target`); messageId = target.messageId || '' }
      catch { /* 原消息已删除时仍可打开会话。 */ }
    }
    if (disposed) return false
    window.focus(); openChat({ projectId, projectType, messageId, syncSidebar: true })
    if (!item.is_read && !reading.has(String(item.id))) {
      reading.add(String(item.id))
      try { await markNotificationRead(item.id); item.is_read = true }
      catch { if (showError) ElMessage.error('会话已打开，聊天提醒暂未标为已读，请重试') }
      finally { reading.delete(String(item.id)) }
    }
    return true
  }
  async function activateConversationNotice(item) {
    notificationAcknowledgements.acknowledge(item.id)
    openFullscreen(); await nextTick()
    window.dispatchEvent(new CustomEvent('chat-show-notifications'))
    try { await markNotificationRead(item.id); window.dispatchEvent(new CustomEvent('business-notifications-changed')) } catch { /* 列表仍允许重新标记已读。 */ }
  }
  function display(notification) {
    if (isConversationNotice(notification)) {
      if (!disposed && !notification.is_read && !notificationAcknowledgements.has(notification.id)) showDesktopNotification(notification, () => activateConversationNotice(notification))
      return
    }
    if (disposed || notification.is_read || notificationAcknowledgements.has(notification.id) || !isChatMentionNotification(notification)) return
    // 仅 @ 提及与消息数字提醒一致；桌面不可用时也不回退到网页弹窗。
    showDesktopNotification(notification, () => activateNotification(notification))
  }
  async function poll(initial = false, force = false) {
    if (disposed || !localStorage.getItem('token')) return
    if (force) { controller?.abort(); loading = false; pendingInitial = false }
    if (loading) { pendingInitial ||= initial; return }
    const version = ++generation, current = new AbortController()
    loading = true; controller = current
    const actor = localStorage.getItem('user_id')
    try {
      const [rows, conversationRows] = await Promise.all([
        getNotifications({ channel: 'chat', limit: initial ? 100 : 10, ...(initial ? { unread_only: true } : {}) }, { signal: current.signal }),
        getNotifications({ channel: 'business', notification_types: CONVERSATION_NOTIFICATION_TYPES, limit: 10, unread_only: true }, { signal: current.signal }),
      ])
      if (disposed || version !== generation || actor !== localStorage.getItem('user_id')) return
      const items = [...(Array.isArray(rows) ? rows : []).filter(isChatNotification), ...(Array.isArray(conversationRows) ? conversationRows : []).filter(isConversationNotice)]
      for (const item of items.slice().reverse()) {
        const fresh = remember(item.id)
        if (fresh) display(item)
      }
    } catch { /* 离线时保留会话未读与现有提醒，后续轮询重试。 */ }
    finally { if (version === generation) { loading = false; if (pendingInitial) { pendingInitial = false; poll(true) } } }
  }
  onMounted(() => {
    poll(true); timer = window.setInterval(() => poll(), 10000)
    cleanups.push(subscribe('notification', payload => {
      const item = payload?.notification
      if (item && (isChatNotification(item) || isConversationNotice(item)) && remember(item.id)) display(item)
    }))
    cleanups.push(subscribe('connected', () => poll(true)))
    cleanups.push(subscribe('foreground', () => poll(true, true)))
  })
  onBeforeUnmount(() => {
    disposed = true; ++generation; controller?.abort(); window.clearInterval(timer); cleanups.forEach(cleanup => cleanup())
  })
}
