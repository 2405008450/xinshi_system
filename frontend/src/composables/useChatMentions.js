import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe } from '@/utils/realtimeSocket'

export function useChatMentions(keyword, active, filters = ref({}), anchor = ref('')) {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const hasMore = ref(false)
  let nextBefore = null
  let generation = 0
  let controller
  let timer
  let eventTimer
  let cleanup = []

  async function load({ append = false, background = false } = {}) {
    if (!active.value || (background && loading.value) || (append && (!hasMore.value || loading.value))) return
    controller?.abort()
    const current = new AbortController()
    controller = current
    const version = ++generation
    const userId = localStorage.getItem('user_id')
    const params = { keyword: keyword.value, project_type: filters.value.projectType || undefined,
      project_status: filters.value.projectStatus || undefined, project_id: filters.value.projectId || undefined }
    const target = background ? Math.max(50, items.value.length) : 50
    const collected = []
    let before = append ? nextBefore : null
    loading.value = true
    error.value = ''
    if (!append && !background) { items.value = []; total.value = 0; hasMore.value = false; nextBefore = null }
    try {
      let data
      // 实时刷新保留已展开的历史范围，避免浏览旧消息时突然跳回第一页。
      do {
        data = await chatRequest('mentions', { params: { ...params, before, limit: 50 }, signal: current.signal })
        if (version !== generation || userId !== localStorage.getItem('user_id')) return
        collected.push(...(data.items || []))
        before = data.nextBefore
      } while (data.hasMore && before && ((background && collected.length < target) ||
        (!append && anchor.value && !collected.some(row => row.messageId === anchor.value))))
      const rows = append ? [...items.value, ...collected] : collected
      items.value = [...new Map(rows.map(row => [row.messageId, row])).values()]
      total.value = data.total || 0
      hasMore.value = !!data.hasMore
      nextBefore = data.nextBefore
    } catch (e) {
      if (version === generation && !current.signal.aborted) error.value = e.detail || e.message || '提及消息加载失败'
    } finally {
      if (version === generation) loading.value = false
    }
  }

  function refresh() {
    clearTimeout(eventTimer)
    if (active.value) eventTimer = setTimeout(() => load({ background: true }), 100)
  }
  function cancel() { ++generation; controller?.abort(); clearTimeout(eventTimer); loading.value = false }
  watch(keyword, () => load())
  watch(filters, () => load(), { deep: true })
  watch(active, value => { if (value) load(); else cancel() })
  onMounted(() => {
    if (active.value) load()
    cleanup = ['annotation_chat_changed', 'chat_sessions_changed', 'chat_message', 'notification', 'connected'].map(event => subscribe(event, refresh))
    timer = setInterval(refresh, 15000)
  })
  onBeforeUnmount(() => { cancel(); clearInterval(timer); cleanup.forEach(fn => fn()) })
  return { items, total, loading, error, hasMore, reload: () => load(), refresh: () => load({ background: true }), loadMore: () => load({ append: true }) }
}
