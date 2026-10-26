import { onBeforeUnmount, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'

export function useDesktopPresence(userIds, active) {
  const statuses = ref({}), loading = ref(false)
  let controller, generation = 0, timer
  async function refresh() {
    controller?.abort(); const version = ++generation
    const ids = [...new Set(userIds.value.map(String))]
    if (!active.value || !ids.length) { statuses.value = {}; loading.value = false; return }
    const current = new AbortController(), actor = localStorage.getItem('user_id')
    controller = current; loading.value = true
    try {
      const result = {}
      for (let index = 0; index < ids.length; index += 200) {
        const data = await chatRequest('presence', { method: 'post', data: { userIds: ids.slice(index, index + 200) }, signal: current.signal })
        if (version !== generation || actor !== localStorage.getItem('user_id')) return
        for (const item of data.items) result[item.userId] = item.desktopOnline
      }
      statuses.value = result
    } catch { if (version === generation) statuses.value = {} }
    finally { if (version === generation) loading.value = false }
  }
  watch(() => [active.value, userIds.value.join(',')], () => {
    clearInterval(timer); statuses.value = {}; refresh()
    if (active.value) timer = setInterval(refresh, 15000)
  }, { immediate: true })
  onBeforeUnmount(() => { ++generation; controller?.abort(); clearInterval(timer) })
  return { statuses, loading }
}
