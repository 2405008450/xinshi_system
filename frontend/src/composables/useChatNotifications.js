import '@/components/chat/chatNotifications.css'
import { h, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { getNotifications, markNotificationRead } from '@/api/notifications'
import { chatRequest } from '@/api/projectChat'
import { createChatNotificationFeed, isPersistentChatNotification, isVisibleConversation } from '@/utils/chatNotificationPolicy'
import { isChatWindowVisible } from '@/composables/useProjectChatDock'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { subscribe } from '@/utils/realtimeSocket'
import { showDesktopNotification } from '@/utils/desktopNotifications'
import { isChatNotification, isChatAttentionNotification } from '@/utils/notificationChannels'
import { notificationAcknowledgements } from '@/utils/notificationAcknowledgements'

/** 聊天独立承接留言、提及和群邀请，通知铃铛仅负责业务提醒。 */
export function useChatNotifications() {
  const { openChat, state } = useProjectChatDock()
  const feed = createChatNotificationFeed(), activeMentionNotifications = new Map(), reading = new Set(), tracked = new Set()
  let timer, controller, loading = false, disposed = false, generation = 0, pendingInitial = false
  const cleanups = []
  const remember = id => feed.remember(id)
  const closeMentionNotification = id => {
    tracked.delete(String(id))
    const instance = activeMentionNotifications.get(String(id))
    activeMentionNotifications.delete(String(id)); instance?.close()
  }
  async function activateNotification(item, showError = false) {
    notificationAcknowledgements.acknowledge(item.id)
    closeMentionNotification(item.id)
    const projectType = item.related_project_type || (String(item.notification_type).startsWith('direct_chat') ? 'direct' : 'translation')
    const projectId = item.related_entity_id || item.related_project_id
    if (!projectId) { if (showError) ElMessage.info('关联会话已不可用'); return false }
    let messageId = ''
    if (!String(item.notification_type).endsWith('_invite')) {
      try { const target = await chatRequest(`mentions/${item.id}/target`); messageId = target.messageId || '' }
      catch { /* 原消息已删除时仍可打开会话。 */ }
    }
    if (disposed) return false
    window.focus(); openChat({ projectId, projectType, messageId, syncSidebar: true })
    if (!item.is_read && !reading.has(String(item.id))) {
      reading.add(String(item.id))
      try { await markNotificationRead(item.id); item.is_read = true; closeMentionNotification(item.id) }
      catch { if (showError) ElMessage.error('会话已打开，聊天提醒暂未标为已读，请重试') }
      finally { reading.delete(String(item.id)) }
    }
    return true
  }
  function display(notification) {
    if (disposed || notification.is_read || notificationAcknowledgements.has(notification.id) || !isChatAttentionNotification(notification)) return
    const persistent = isPersistentChatNotification(notification)
    if (!persistent && isVisibleConversation(notification, state, isChatWindowVisible, document)) return
    const id = String(notification.id)
    if (activeMentionNotifications.has(id)) return
    tracked.add(id)
    const showFallback = () => {
      if (disposed || activeMentionNotifications.has(id) || notificationAcknowledgements.has(id)) return
      if (!persistent && isVisibleConversation(notification, state, isChatWindowVisible, document)) return
      const instance = ElNotification({
        title: notification.title || '聊天提醒',
        message: h('div', { class: 'mention-notification__body' }, [
          h('div', { class: 'mention-notification__summary' }, notification.content || ''),
          h('div', { class: 'mention-notification__hint' }, '点击打开沟通'),
        ]),
        type: 'info', position: 'top-right', duration: persistent ? 0 : 4000, showClose: true,
        customClass: 'mention-notification',
        onClick: () => activateNotification(notification, true),
        onClose: () => {
          // 同步关闭和组件卸载会先移出 Map；只有用户关闭持续提醒才确认。
          if (activeMentionNotifications.delete(id) && persistent) notificationAcknowledgements.acknowledge(id)
        },
      })
      activeMentionNotifications.set(id, instance)
    }
    const desktopShown = showDesktopNotification(notification, () => activateNotification(notification), { onError: showFallback })
    if (persistent || !desktopShown) showFallback()
  }
  async function poll(initial = false, force = false) {
    if (disposed || !localStorage.getItem('token')) return
    if (force) { controller?.abort(); loading = false; pendingInitial = false }
    if (loading) { pendingInitial ||= initial; return }
    const version = ++generation, current = new AbortController()
    loading = true; controller = current
    const actor = localStorage.getItem('user_id')
    try {
      // 按 ID 核对仍在显示的通知，避免大量新消息挤出旧通知后无法关闭。
      const ids = [...tracked]
      for (let offset = 0; offset < ids.length; offset += 100) {
        const batch = ids.slice(offset, offset + 100)
        const statuses = await getNotifications({ channel: 'chat', limit: 100, notification_ids: batch }, { signal: current.signal })
        if (disposed || version !== generation || actor !== localStorage.getItem('user_id')) return
        const unread = new Set((Array.isArray(statuses) ? statuses : []).filter(row => !row.is_read).map(row => String(row.id)))
        batch.filter(id => !unread.has(id)).forEach(id => notificationAcknowledgements.acknowledge(id))
      }
      const items = []
      // 重连期间可能超过一页；一直读取到上次基线，避免仅取最新十条漏消息。
      for (let skip = 0; ; skip += 100) {
        const rows = await getNotifications({ channel: 'chat', limit: 100, skip, ...(!feed.initialized ? { unread_only: true } : {}) }, { signal: current.signal })
        if (disposed || version !== generation || actor !== localStorage.getItem('user_id')) return
        const page = (Array.isArray(rows) ? rows : []).filter(isChatNotification)
        items.push(...page)
        if (!feed.initialized || page.length < 100 || (Date.parse(page.at(-1)?.created_at) || 0) < feed.boundary) break
      }
      for (const item of items) {
        if (item.is_read) { notificationAcknowledgements.acknowledge(item.id); closeMentionNotification(item.id) }
      }
      for (const item of feed.consume(items)) display(item)
    } catch { /* 离线时保留会话未读与现有提醒，后续轮询重试。 */ }
    finally { if (version === generation) { loading = false; if (pendingInitial) { pendingInitial = false; poll(true) } } }
  }
  onMounted(() => {
    cleanups.push(notificationAcknowledgements.subscribe(closeMentionNotification))
    poll(true); timer = window.setInterval(() => poll(), 10000)
    cleanups.push(subscribe('notification', payload => {
      const item = payload?.notification
      if (item && isChatNotification(item) && remember(item.id)) display(item)
    }))
    cleanups.push(subscribe('connected', () => poll(true)))
    for (const event of ['chat_sessions_changed', 'annotation_chat_changed', 'direct_chat_changed']) {
      cleanups.push(subscribe(event, () => poll()))
    }
    cleanups.push(subscribe('foreground', () => poll(true, true)))
  })
  onBeforeUnmount(() => {
    disposed = true; ++generation; controller?.abort(); window.clearInterval(timer); cleanups.forEach(cleanup => cleanup())
    const instances = [...activeMentionNotifications.values()]; activeMentionNotifications.clear(); instances.forEach(instance => instance.close())
  })
}
