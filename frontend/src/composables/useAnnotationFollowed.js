import { onBeforeUnmount, onMounted, ref } from 'vue'
import { annotationChatRequest } from '@/api/projectChat'
import { subscribe, ensureConnected } from '@/utils/realtimeSocket'
import { hasPermission } from '@/utils/permission'
import { isChatWindowVisible, useProjectChatDock } from '@/composables/useProjectChatDock'

const followed = ref([])
const total = ref(0)
const error = ref('')
let users = 0
let timer = 0
let pending = false
let rerun = false
let cleanup = []

async function refresh() {
  if (!hasPermission('projects:read')) return
  if (pending) {
    rerun = true
    return
  }
  pending = true
  try {
    const data = await annotationChatRequest('', 'unread')
    followed.value = data.followedItems || []
    total.value = data.total || 0
    error.value = ''
    const { state } = useProjectChatDock()
    state.windows.filter(item => item.projectType === 'annotation').forEach((item) => {
      const unread = data.items.find(row => String(row.projectId) === String(item.projectId))?.unread || 0
      item.unread = isChatWindowVisible(item) ? 0 : unread
    })
  } catch {
    error.value = '未读消息暂时无法加载'
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
    subscribe('connected', refresh),
  ]
  timer = window.setInterval(refresh, 15000)
}

function stop() {
  if (users !== 0) return
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
  return { followed, total, error, refresh }
}
