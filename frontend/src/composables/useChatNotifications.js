import '@/components/chat/chatNotifications.css'
import { h, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { getNotifications, markNotificationRead } from '@/api/notifications'
import { chatRequest } from '@/api/projectChat'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { subscribe } from '@/utils/realtimeSocket'
import { showDesktopNotification } from '@/utils/desktopNotifications'
import { isChatNotification, isChatMentionNotification, isChatAttentionNotification } from '@/utils/notificationChannels'

/** 聊天独立承接留言、提及和群邀请，通知铃铛仅负责业务提醒。 */
export function useChatNotifications() {
  const { openChat } = useProjectChatDock()
  const seen = new Set(), activeMentionNotifications = new Map(), reading = new Set()
  let timer, controller, loading = false, disposed = false, generation = 0, pendingInitial = false
  const cleanups = []
  const remember = id => {
    if (!id || seen.has(String(id))) return false
    seen.add(String(id))
    while (seen.size > 200) seen.delete(seen.values().next().value)
    return true
  }
  const closeMentionNotification = id => {
    const instance = activeMentionNotifications.get(String(id))
    activeMentionNotifications.delete(String(id)); instance?.close()
  }
  async function activateNotification(item, showError = false) {
    const projectType = item.related_project_type || (String(item.notification_type).startsWith('direct_chat') ? 'direct' : 'translation')
    const projectId = item.related_entity_id || item.related_project_id
    if (!projectId) { if (showError) ElMessage.info('关联会话已不可用'); return false }
    let messageId = ''
    if (isChatMentionNotification(item)) {
      try { const target = await chatRequest(`mentions/${item.id}/target`); messageId = target.messageId || '' }
      catch { /* 原消息已删除时仍可打开会话。 */ }
    }
    if (disposed) return false
    window.focus(); openChat({ projectId, projectType, messageId })
    if (!item.is_read && !reading.has(String(item.id))) {
      reading.add(String(item.id))
      try { await markNotificationRead(item.id); item.is_read = true; closeMentionNotification(item.id) }
      catch { if (showError) ElMessage.error('会话已打开，聊天提醒暂未标为已读，请重试') }
      finally { reading.delete(String(item.id)) }
    }
    return true
  }
  function display(notification) {
    if (disposed || notification.is_read || !isChatAttentionNotification(notification)) return
    const persistent = isChatMentionNotification(notification) || String(notification.notification_type).endsWith('_invite')
    const id = String(notification.id)
    if (activeMentionNotifications.has(id)) return
    const desktopShown = showDesktopNotification(notification, () => activateNotification(notification))
    if (!persistent && desktopShown) return
    const instance = ElNotification({
      title: notification.title || '聊天提醒',
      message: h('div', { class: 'mention-notification__body' }, [
        h('div', { class: 'mention-notification__summary' }, notification.content || ''),
        h('div', { class: 'mention-notification__hint' }, '点击打开沟通'),
      ]),
      type: 'info', position: 'top-right', duration: persistent ? 0 : 4000, showClose: true,
      customClass: 'mention-notification',
      onClick: () => activateNotification(notification, true),
      onClose: () => activeMentionNotifications.delete(id),
    })
    activeMentionNotifications.set(id, instance)
  }
  async function poll(initial = false, force = false) {
    if (disposed || !localStorage.getItem('token')) return
    if (force) { controller?.abort(); loading = false; pendingInitial = false }
    if (loading) { pendingInitial ||= initial; return }
    const version = ++generation, current = new AbortController()
    loading = true; controller = current
    const actor = localStorage.getItem('user_id')
    try {
      const rows = await getNotifications({ channel: 'chat', limit: initial ? 100 : 10, ...(initial ? { unread_only: true } : {}) }, { signal: current.signal })
      if (disposed || version !== generation || actor !== localStorage.getItem('user_id')) return
      const items = (Array.isArray(rows) ? rows : []).filter(isChatNotification)
      for (const item of items.slice().reverse()) {
        const fresh = remember(item.id)
        if (initial ? isChatMentionNotification(item) || String(item.notification_type).endsWith('_invite') : fresh) display(item)
      }
    } catch { /* 离线时保留会话未读与现有提醒，后续轮询重试。 */ }
    finally { if (version === generation) { loading = false; if (pendingInitial) { pendingInitial = false; poll(true) } } }
  }
  onMounted(() => {
    poll(true); timer = window.setInterval(() => poll(), 10000)
    cleanups.push(subscribe('notification', payload => {
      const item = payload?.notification
      if (item && isChatNotification(item) && remember(item.id)) display(item)
    }))
    cleanups.push(subscribe('connected', () => poll(true)))
    cleanups.push(subscribe('foreground', () => poll(true, true)))
  })
  onBeforeUnmount(() => {
    disposed = true; ++generation; controller?.abort(); window.clearInterval(timer); cleanups.forEach(cleanup => cleanup())
    const instances = [...activeMentionNotifications.values()]; activeMentionNotifications.clear(); instances.forEach(instance => instance.close())
  })
}
