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
let updateScheduler
let retryTimer
let retryPending = false
let cleanup = []
let generation = 0
let controller
let updateController
let catalogUserId
const pendingSessions = new Set()
let lastSuccessfulRefresh = 0
const RATE_LIMIT_STALE_MS = 60000
const SESSION_UPDATE_BATCH_SIZE = 12
const SESSION_UPDATE_MIN_INTERVAL_MS = 8000
const SESSION_UPDATE_DELAY_MS = 1000
const SESSION_UPDATE_JITTER_MS = 2000

function refresh(options = {}) {
  if (!refreshScheduler) return Promise.resolve()
  if (queueSessionUpdate(options)) {
    return Promise.resolve()
  }
  if (options?.force === true) {
    // 前台恢复时旧连接可能已挂起；废弃旧响应，恢复请求与随后的连接事件仍合并。
    ++generation
    cancelRetry()
    retryPending = false
    controller?.abort()
    updateController?.abort()
    refreshScheduler.stop()
    refreshScheduler = createScheduler()
  }
  return refreshScheduler.schedule()
}

function queueSessionUpdate(event) {
  const kind = event?.projectType ?? ({
    annotation_chat_changed: 'annotation',
    direct_chat_changed: 'direct',
  })[event?.type]
  if (!['annotation', 'translation', 'direct', 'discussion'].includes(kind) ||
    !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(event?.projectId)) return false
  pendingSessions.add(`${kind}:${event.projectId.toLowerCase()}`)
  if (catalogUserId && !controller) void updateScheduler?.schedule()
  return true
}

function refreshForStateEvent(event) {
  if (!event?.membersChanged && ['message', 'read', 'state'].includes(event?.kind) && queueSessionUpdate(event)) return
  void refresh()
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

function applySessions(rows, updatedKeys) {
  sessions.value = rows
  mentionTotal.value = rows.reduce((sum, item) => sum + (item.mentionUnread || 0), 0)
  total.value = followed.value.reduce((sum, item) => sum + (item.unread || 0), 0)
  const byKey = new Map(rows.map(row => [row.key, row]))
  const { state } = useProjectChatDock()
  state.windows.forEach(item => {
    const key = item.conversationKey || item.key
    if (updatedKeys && !updatedKeys.has(key)) return
    const session = byKey.get(key)
    item.unread = session?.unread ?? 0
    item.mentionUnread = session?.mentionUnread ?? 0
    item.projectStatus = session?.projectStatus || ''
    if (session && item.projectType === 'discussion') item.title = session.title
  })
}

async function fetchSessionUpdates() {
  const userId = localStorage.getItem('user_id')
  if (controller || !userId || userId !== catalogUserId || !pendingSessions.size) return
  const version = generation
  const keys = new Set([...pendingSessions].slice(0, SESSION_UPDATE_BATCH_SIZE))
  keys.forEach(key => pendingSessions.delete(key))
  const current = new AbortController()
  updateController = current
  try {
    const data = await chatRequest('sessions/updates', { params: { keys: [...keys].join(',') }, signal: current.signal })
    if (current.signal.aborted || version !== generation || userId !== localStorage.getItem('user_id')) return
    const merged = new Map(sessions.value.map(row => [row.key, row]))
    const returned = new Map(data.items.map(row => [row.key, row]))
    for (const key of keys) {
      if (returned.has(key)) merged.set(key, returned.get(key))
      else merged.delete(key)
    }
    applySessions([...merged.values()], keys)
  } catch {
    // 周期校准和连接恢复会补齐目录。单次局部读取失败不挤占全量目录配额。
  } finally {
    if (updateController === current) updateController = undefined
    if (users && userId === catalogUserId && userId === localStorage.getItem('user_id')) {
      if (version !== generation) keys.forEach(key => pendingSessions.add(key))
      if (!controller && pendingSessions.size) void updateScheduler?.schedule()
    }
  }
}

async function fetchSessions() {
  if (!localStorage.getItem('user_id')) return
  const retry = retryPending
  retryPending = false
  cancelRetry()
  const version = ++generation
  const userId = localStorage.getItem('user_id')
  const current = new AbortController()
  controller = current
  updateController?.abort()
  try {
    const data = await chatRequest('sessions', { signal: current.signal, timeout: 20000 })
    if (version !== generation || userId !== localStorage.getItem('user_id')) return
    lastSuccessfulRefresh = Date.now()
    if (catalogUserId && catalogUserId !== userId) pendingSessions.clear()
    catalogUserId = userId
    applySessions(data.items || [])
    mentionTotal.value = data.mentionTotal || 0
    applySessionCategories(data.sessionCategories)
    phaseOneEnabled.value = !!data.phaseOneEnabled
    mentionHistoryTotal.value = data.mentionHistoryTotal || 0
    annotationMentionCounts.value = data.annotationMentionCounts || []
    error.value = ''
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
  } finally {
    if (controller === current) {
      controller = undefined
      if (catalogUserId === userId && pendingSessions.size) void updateScheduler?.schedule()
    }
  }
}

function start() {
  if (users !== 1) return
  refreshScheduler = createScheduler()
  updateScheduler = createCoalescedRefresh(fetchSessionUpdates, {
    debounceMs: SESSION_UPDATE_DELAY_MS + Math.floor(Math.random() * SESSION_UPDATE_JITTER_MS),
    minIntervalMs: SESSION_UPDATE_MIN_INTERVAL_MS,
    visible: () => document.visibilityState !== 'hidden',
  })
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
    subscribe('chat_message', event => queueSessionUpdate(event)),
    subscribe('chat_remote_message_changed', refreshForStateEvent),
    subscribe('chat_mention_changed', refresh),
    subscribe('chat_realtime_recovered', refresh),
    subscribe('notification', payload => {
      const item = payload?.notification
      const type = String(item?.notification_type || '').trim().toLowerCase()
      if (CONVERSATION_NOTIFICATION_TYPES.includes(type) ||
        (isChatNotification(item) && (type.endsWith('_mention') || type.endsWith('_invite')))) void refresh()
      else if (isChatNotification(item)) queueSessionUpdate({
        projectType: item.related_project_type, projectId: item.related_entity_id || item.related_project_id,
      })
    }),
    subscribe('connected', refresh),
    subscribe('foreground', () => refresh({ force: true })),
  ]
  // 实时事件继续合并刷新；跨环境仍以较低频率兜底，避免所有客户端同时请求。
  timer = window.setInterval(() => {
    if (document.visibilityState === 'hidden' || Date.now() - lastSuccessfulRefresh < 55000) return
    void refresh()
    refreshTopics().catch(() => {})
  }, 60000 + Math.floor(Math.random() * 10000))
}

function stop() {
  if (users !== 0) return
  ++generation
  refreshScheduler?.stop()
  refreshScheduler = null
  updateScheduler?.stop()
  updateScheduler = null
  controller?.abort()
  controller = undefined
  updateController?.abort()
  updateController = undefined
  cancelRetry()
  pendingSessions.clear()
  catalogUserId = undefined
  retryPending = false
  lastSuccessfulRefresh = 0
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
