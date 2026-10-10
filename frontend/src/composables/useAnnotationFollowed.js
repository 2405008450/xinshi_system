import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe, ensureConnected } from '@/utils/realtimeSocket'
import { useProjectChatDock } from '@/composables/useProjectChatDock'

const sessions = ref([])
const followed = computed(() => sessions.value.filter(s => s.kind === 'annotation' && s.following !== false).map(s => ({ ...s, projectName: s.title, orderNo: s.subtitle })))
const mentionTotal = ref(0)
const phaseOneEnabled = ref(false)
const total = ref(0)
const error = ref('')
let users = 0
let timer = 0
let pending = false
let rerun = false
let cleanup = []
let generation = 0
let controller

async function refresh() {
  if (!localStorage.getItem('user_id')) return
  if (pending) {
    rerun = true
    return
  }
  pending = true
  const version = generation
  const userId = localStorage.getItem('user_id')
  controller = new AbortController()
  try {
    const data = await chatRequest('sessions', { signal: controller.signal })
    if (version !== generation || userId !== localStorage.getItem('user_id')) return
    sessions.value = data.items || []
    phaseOneEnabled.value = !!data.phaseOneEnabled
    mentionTotal.value = data.mentionTotal || 0
    total.value = followed.value.reduce((sum, item) => sum + (item.unread || 0), 0)
    error.value = ''
    const { state } = useProjectChatDock()
    state.windows.forEach((item) => {
      const session = sessions.value.find(row => row.key === item.key)
      if (session) { item.unread = session.unread; item.mentionUnread = session.mentionUnread }
    })
  } catch {
    if (version === generation && !controller.signal.aborted) error.value = '未读消息暂时无法加载'
  } finally {
    pending = false
    if (rerun) {
      rerun = false
      refresh()
    }
  }
}

function start() {
  if (users !== 1) return
  refresh()
  ensureConnected()
  cleanup = [
    subscribe('annotation_chat_changed', refresh),
    subscribe('direct_chat_changed', refresh),
    subscribe('chat_sessions_changed', refresh),
    subscribe('chat_message', refresh),
    subscribe('notification', refresh),
    subscribe('connected', refresh),
  ]
  timer = window.setInterval(refresh, 15000)
}

function stop() {
  if (users !== 0) return
  ++generation
  controller?.abort()
  sessions.value = []
  total.value = 0
  mentionTotal.value = 0
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
  return { followed, sessions, total, mentionTotal, phaseOneEnabled, error, refresh }
}
