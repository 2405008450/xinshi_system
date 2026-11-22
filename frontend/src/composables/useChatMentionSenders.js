import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe } from '@/utils/realtimeSocket'

export function useChatMentionSenders(active, paramsRef = ref({ mentionKind: 'personal' })) {
  const items = ref([])
  const total = ref(0)
  const unreadTotal = ref(0)
  const loading = ref(false)
  let generation = 0
  let controller
  let timer
  let eventTimer
  let cleanup = []

  async function load({ background = false } = {}) {
    if (!active.value || (background && loading.value)) return
    controller?.abort()
    const current = new AbortController()
    controller = current
    const version = ++generation
    const userId = localStorage.getItem('user_id')
    const filter = paramsRef.value || {}
    loading.value = true
    try {
      const data = await chatRequest('mentions/senders', {
        params: {
          keyword: filter.keyword || undefined,
          project_type: filter.projectType || undefined,
          project_status: filter.projectStatus || undefined,
          project_id: filter.projectId || undefined,
          mention_kind: filter.mentionKind || undefined,
        },
        signal: current.signal,
      })
      if (version !== generation || userId !== localStorage.getItem('user_id')) return
      items.value = Array.isArray(data.items) ? data.items : []
      total.value = Number(data.total) || 0
      unreadTotal.value = Number(data.unreadTotal) || 0
    } catch {
      // 静默忽略中止或瞬时网络错误，下次刷新自动恢复。
    } finally {
      if (version === generation) loading.value = false
    }
  }

  function refresh() {
    clearTimeout(eventTimer)
    if (active.value) eventTimer = setTimeout(() => load({ background: true }), 150)
  }

  function cancel() {
    ++generation
    controller?.abort()
    clearTimeout(eventTimer)
    loading.value = false
  }

  watch(paramsRef, () => load(), { deep: true })
  watch(active, value => { if (value) load(); else cancel() })
  onMounted(() => {
    if (active.value) load()
    cleanup = ['annotation_chat_changed', 'chat_sessions_changed', 'chat_message_acknowledgement', 'chat_message', 'notification', 'connected'].map(event => subscribe(event, refresh))
    timer = setInterval(refresh, 15000)
  })
  onBeforeUnmount(() => {
    cancel()
    clearInterval(timer)
    cleanup.forEach(fn => fn())
  })
  return { items, total, unreadTotal, loading, reload: () => load() }
}
