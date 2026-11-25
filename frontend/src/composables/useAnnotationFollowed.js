import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe, ensureConnected } from '@/utils/realtimeSocket'
import { useProjectChatDock, refreshOpenAnnotationStatuses } from '@/composables/useProjectChatDock'
import { applySessionCategories } from '@/composables/useChatSessionCategories'
import { useChatTopics } from '@/composables/useChatTopics'
import { createCoalescedRefresh } from '@/utils/coalescedRefresh'
import { isChatNotification, CONVERSATION_NOTIFICATION_TYPES } from '@/utils/notificationChannels'
const { refresh: refreshTopics } = useChatTopics()

const sessions = ref([])
const followed = computed(() => sessions.value.filter(s => s.kind === 'annotation' && s.following !== false).map(s => ({ ...s, projectName: s.title, orderNo: s.subtitle })))
const mentionTotal = ref(0)
const mentionHistoryTotal = ref(0)
const annotationMentionCounts = ref([])
const phaseOneEnabled = ref(false)
const total = ref(0)
const error = ref('')
let users = 0
let timer = 0
let refreshScheduler
let messageRefreshTimer
let retryTimer
let retryPending = false
let cleanup = []
let generation = 0
let controller
let lastSuccessfulRefresh = 0
let lastRefreshStarted = 0
const RATE_LIMIT_STALE_MS = 60000
const MESSAGE_REFRESH_GAP_MS = 12000
const MESSAGE_REFRESH_BASE_DELAY_MS = 2000
const MESSAGE_REFRESH_JITTER_MS = 4000

function refresh(options = {}) {
  if (!refreshScheduler) return Promise.resolve()
  if (options?.messageActivity === true) {
    queueMessageRefresh()
    return Promise.resolve()
  }
  if (options?.force === true) {
    // 前台恢复时旧连接可能已挂起；废弃旧响应，恢复请求与随后的连接事件仍合并。
    ++generation
    cancelRetry()
    retryPending = false
    clearMessageRefresh()
    controller?.abort()
    refreshScheduler.stop()
    refreshScheduler = createScheduler()
  }
  return refreshScheduler.schedule()
}

function clearMessageRefresh() {
  if (messageRefreshTimer !== undefined) window.clearTimeout(messageRefreshTimer)
  messageRefreshTimer = undefined
}

function queueMessageRefresh() {
  if (!refreshScheduler || document.visibilityState === 'hidden' || messageRefreshTimer !== undefined) return
  const elapsed = Date.now() - lastRefreshStarted
  const delay = Math.max(0, MESSAGE_REFRESH_GAP_MS - elapsed)
    + MESSAGE_REFRESH_BASE_DELAY_MS + Math.floor(Math.random() * MESSAGE_REFRESH_JITTER_MS)
  messageRefreshTimer = window.setTimeout(() => {
    messageRefreshTimer = undefined
    void refresh()
  }, delay)
}

function refreshForStateEvent(event) {
  if (!event?.membersChanged && ['message', 'read', 'state'].includes(event?.kind)) queueMessageRefresh()
  else void refresh()
}
function createScheduler() {
  return createCoalescedRefresh(fetchSessions, {
    visible: () => document.visibilityState !== 'hidden',
  })
}


function cancelRetry() {
  if (retryTimer !== undefined) window.clearTimeout(retryTimer)
  retryTimer = undefined
}

function transientFailure(cause) {
  return [429, 502, 503, 504].includes(cause.response?.status) ||
    ['ERR_NETWORK', 'ECONNABORTED', 'ETIMEDOUT'].includes(cause.code)
}

async function fetchSessions() {
  if (!localStorage.getItem('user_id')) return
  lastRefreshStarted = Date.now()
  clearMessageRefresh()
  const retry = retryPending
  retryPending = false
  cancelRetry()
  const version = ++generation
  const userId = localStorage.getItem('user_id')
  const current = new AbortController()
  controller = current
  try {
    const data = await chatRequest('sessions', { signal: current.signal, timeout: 20000 })
    if (version !== generation || userId !== localStorage.getItem('user_id')) return
    lastSuccessfulRefresh = Date.now()
    sessions.value = data.items || []
    applySessionCategories(data.sessionCategories)
    phaseOneEnabled.value = !!data.phaseOneEnabled
    mentionTotal.value = data.mentionTotal || 0
    mentionHistoryTotal.value = data.mentionHistoryTotal || 0
    annotationMentionCounts.value = data.annotationMentionCounts || []
    total.value = followed.value.reduce((sum, item) => sum + (item.unread || 0), 0)
    error.value = ''
    const { state } = useProjectChatDock()
    state.windows.forEach((item) => {
      const session = sessions.value.find(row => row.key === (item.conversationKey || item.key))
      if (session) { item.unread = session.unread; item.mentionUnread = session.mentionUnread; item.projectStatus = session.projectStatus || ''; if (item.projectType === 'discussion') item.title = session.title }
      else { item.unread = 0; item.mentionUnread = 0 }
    })
    void refreshOpenAnnotationStatuses(sessions.value).catch(() => {})
  } catch (cause) {
    if (version === generation && !current.signal.aborted) {
      const rateLimited = cause.response?.status === 429
      if (!retry && transientFailure(cause)) {
        const retryAfter = Number(cause.response?.headers?.['retry-after'])
        const delay = Math.max(1000, Math.min(10000, (retryAfter || 1) * 1000))
          + (rateLimited ? Math.floor(Math.random() * 1500) : 0)
        retryTimer = window.setTimeout(() => {
          retryTimer = undefined
          if (version === generation && userId === localStorage.getItem('user_id')) {
            retryPending = true
            void refresh()
          }
        }, delay)
      } else if (!rateLimited || !lastSuccessfulRefresh || Date.now() - lastSuccessfulRefresh >= RATE_LIMIT_STALE_MS) {
        console.warn('会话目录刷新失败', JSON.stringify({ code: cause.code, status: cause.response?.status, message: cause.message }))
        error.value = '未读消息暂时无法加载'
      }
    }
  }
}

function start() {
  if (users !== 1) return
  refreshScheduler = createScheduler()
  refreshScheduler.schedule({ immediate: true })
  refreshTopics().catch(() => {})
  ensureConnected()
  cleanup = [
    subscribe('annotation_chat_changed', refreshForStateEvent),
    subscribe('direct_chat_changed', refreshForStateEvent),
    subscribe('chat_sessions_changed', refreshForStateEvent),
    subscribe('chat_message_acknowledgement', refresh),
    subscribe('chat_conversation_removed', event => {
      window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: { projectType: event.projectType, projectId: event.projectId } }))
      refresh()
    }),
    subscribe('chat_topics_changed', () => refreshTopics(true).catch(() => {})),
    subscribe('chat_message', queueMessageRefresh),
    subscribe('chat_remote_message_changed', refreshForStateEvent),
    subscribe('chat_mention_changed', refresh),
    subscribe('chat_realtime_recovered', refresh),
    subscribe('notification', payload => {
      const item = payload?.notification
      const type = String(item?.notification_type || '').trim().toLowerCase()
      if (CONVERSATION_NOTIFICATION_TYPES.includes(type) ||
        (isChatNotification(item) && (type.endsWith('_mention') || type.endsWith('_invite')))) void refresh()
      else if (isChatNotification(item)) queueMessageRefresh()
    }),
    subscribe('connected', refresh),
    subscribe('foreground', () => refresh({ force: true })),
  ]
  // 实时事件继续合并刷新；跨环境仍以较低频率兜底，避免所有客户端同时请求。
  timer = window.setInterval(() => {
    if (document.visibilityState === 'hidden' || Date.now() - lastSuccessfulRefresh < 25000) return
    void refresh()
    refreshTopics().catch(() => {})
  }, 30000 + Math.floor(Math.random() * 5000))
}

function stop() {
  if (users !== 0) return
  ++generation
  refreshScheduler?.stop()
  refreshScheduler = null
  controller?.abort()
  cancelRetry()
  clearMessageRefresh()
  retryPending = false
  lastSuccessfulRefresh = 0
  lastRefreshStarted = 0
  sessions.value = []
  applySessionCategories(null)
  total.value = 0
  mentionTotal.value = 0
  mentionHistoryTotal.value = 0
  annotationMentionCounts.value = []
  phaseOneEnabled.value = false
  error.value = ''
  window.clearInterval(timer)
  cleanup.forEach(fn => fn())
  cleanup = []
}

export function useAnnotationFollowed() {
  onMounted(() => {
    users += 1
    start()
  })
  onBeforeUnmount(() => {
    users -= 1
    stop()
  })
  return { followed, sessions, total, mentionTotal, mentionHistoryTotal, annotationMentionCounts, phaseOneEnabled, error, refresh }
}
