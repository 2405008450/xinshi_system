import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe } from '@/utils/realtimeSocket'

export function useChatMessageInteractions({ projectId, projectType, messages, active }) {
  const stats = reactive({}), viewsAvailable = ref(null), error = ref('')
  const base = computed(() => `conversations/${projectType.value}/${projectId.value}`)
  const elements = new Map(), visible = new Set(), recorded = new Set()
  let observer, timer, refreshTimer, flushTimer, request, version = 0, disposed = false, posting = false
  let unsubscribe = []
  const foreground = () => active.value && document.visibilityState === 'visible' && document.hasFocus()
  function queueRefresh() { clearTimeout(refreshTimer); refreshTimer = setTimeout(refresh, 180) }
  async function refresh() {
    if (disposed || !active.value || !projectId.value) return
    const ids = [...new Set([...visible, ...messages.value.slice(-100).map(row => String(row.id))])].slice(0, 100)
    if (!ids.length) return
    request?.abort(); request = new AbortController(); const current = ++version
    try {
      const data = await chatRequest(`${base.value}/message-stats`, { method: 'post', data: { messageIds: ids }, signal: request.signal })
      if (disposed || current !== version) return
      viewsAvailable.value = data.viewsAvailable; error.value = ''
      for (const item of data.items || []) stats[String(item.messageId)] = item
      queueFlush()
    } catch (e) { if (current === version && e.code !== 'ERR_CANCELED') error.value = '消息状态暂未加载' }
  }
  function queueFlush() { clearTimeout(flushTimer); flushTimer = setTimeout(flush, 350) }
  async function flush() {
    if (disposed || posting || !foreground() || viewsAvailable.value !== true) return
    const ids = [...visible].filter(id => !recorded.has(id)).slice(0, 100)
    if (!ids.length) return
    posting = true
    try {
      await chatRequest(`${base.value}/message-views`, { method: 'post', data: { messageIds: ids } })
      if (!disposed) ids.forEach(id => recorded.add(id))
    } catch { /* 阅读回执失败不能伪装成功，下次可见时重试。 */ }
    finally { posting = false }
  }
  function observe(el, message) {
    const id = String(message?.id || '')
    if (!id) return
    const previous = elements.get(id)
    if (previous && previous !== el) observer?.unobserve(previous)
    if (!el) { elements.delete(id); visible.delete(id); return }
    el.dataset.interactionMessageId = id; elements.set(id, el); observer?.observe(el)
  }
  const onFocus = () => { queueRefresh(); queueFlush() }
  watch(() => messages.value.map(row => row.id).join(','), queueRefresh)
  watch(active, value => { if (value) onFocus() })
  watch(base, () => {
    ++version; request?.abort(); recorded.clear(); visible.clear()
    for (const key of Object.keys(stats)) delete stats[key]
    viewsAvailable.value = null; queueRefresh()
  })
  onMounted(() => {
    // 使用浏览器视口并计入所有滚动祖先裁切，不能把屏幕外的平铺窗口算作已读。
    observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        const id = entry.target.dataset.interactionMessageId
        if (entry.isIntersecting && entry.intersectionRatio >= .5) visible.add(id)
        else visible.delete(id)
      }
      queueRefresh(); queueFlush()
    }, { root: null, threshold: [0, .5, 1] })
    elements.forEach(el => observer.observe(el))
    for (const type of ['chat_message_interactions', 'annotation_chat_changed', 'direct_chat_changed', 'chat_message', 'chat_sessions_changed']) {
      unsubscribe.push(subscribe(type, event => { if ((!event.projectId || String(event.projectId) === String(projectId.value)) && (!event.projectType || event.projectType === projectType.value)) queueRefresh() }))
    }
    timer = setInterval(() => { if (foreground()) { refresh(); queueFlush() } }, 8000)
    document.addEventListener('visibilitychange', onFocus); window.addEventListener('focus', onFocus)
    queueRefresh()
  })
  onBeforeUnmount(() => {
    disposed = true; ++version; request?.abort(); observer?.disconnect()
    clearInterval(timer); clearTimeout(refreshTimer); clearTimeout(flushTimer); unsubscribe.forEach(fn => fn())
    document.removeEventListener('visibilitychange', onFocus); window.removeEventListener('focus', onFocus)
  })
  return { stats, viewsAvailable, error, observe, refresh }
}
