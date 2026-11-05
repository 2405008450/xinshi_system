import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe, ensureConnected } from '@/utils/realtimeSocket'
import { useProjectChatDock, refreshOpenAnnotationStatuses } from '@/composables/useProjectChatDock'
import { applySessionCategories } from '@/composables/useChatSessionCategories'
import { useChatTopics } from '@/composables/useChatTopics'
import { createCoalescedRefresh } from '@/utils/coalescedRefresh'
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
let cleanup = []
let generation = 0
let controller

function refresh(options = {}) {
  if (!refreshScheduler) return Promise.resolve()
  if (options?.force === true) {
    // 前台恢复时旧连接可能已挂起；废弃旧响应，恢复请求与随后的连接事件仍合并。
    ++generation
    controller?.abort()
    refreshScheduler.stop()
    refreshScheduler = createScheduler()
  }
  return refreshScheduler.schedule()
}

function createScheduler() {
  return createCoalescedRefresh(fetchSessions, {
    visible: () => document.visibilityState !== 'hidden',
  })
}

async function fetchSessions() {
  if (!localStorage.getItem('user_id')) return
  const version = ++generation
  const userId = localStorage.getItem('user_id')
  const current = new AbortController()
  controller = current
  try {
    const data = await chatRequest('sessions', { signal: current.signal, timeout: 20000 })
    if (version !== generation || userId !== localStorage.getItem('user_id')) return
    sessions.value = data.items || []
    applySessionCategories(data.sessionCategories)
    refreshTopics().catch(() => {})
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
    })
    await refreshOpenAnnotationStatuses(sessions.value)
  } catch (cause) {
    if (version === generation && !current.signal.aborted) {
      console.warn('会话目录刷新失败', JSON.stringify({ code: cause.code, status: cause.response?.status, message: cause.message }))
      error.value = '未读消息暂时无法加载'
    }
  }
}

function start() {
  if (users !== 1) return
  refreshScheduler = createScheduler()
  refreshScheduler.schedule({ immediate: true })
  ensureConnected()
  cleanup = [
    subscribe('annotation_chat_changed', refresh),
    subscribe('direct_chat_changed', refresh),
    subscribe('chat_sessions_changed', refresh),
    subscribe('chat_conversation_removed', event => {
      window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: { projectType: event.projectType, projectId: event.projectId } }))
      refresh()
    }),
    subscribe('chat_topics_changed', () => refreshTopics(true).catch(() => {})),
    subscribe('chat_message', refresh),
    subscribe('notification', refresh),
    subscribe('connected', refresh),
    subscribe('foreground', () => refresh({ force: true })),
  ]
  timer = window.setInterval(refresh, 15000)
}

function stop() {
  if (users !== 0) return
  ++generation
  refreshScheduler?.stop()
  refreshScheduler = null
  controller?.abort()
  sessions.value = []
  applySessionCategories(null)
  total.value = 0
  mentionTotal.value = 0
  mentionHistoryTotal.value = 0
  annotationMentionCounts.value = []
  phaseOneEnabled.value = false
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
