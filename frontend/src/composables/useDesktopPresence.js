import { onBeforeUnmount, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { subscribe } from '@/utils/realtimeSocket'

export function useDesktopPresence(userIds, active) {
  const statuses = ref({}), workStatuses = ref({}), loading = ref(false)
  let controller, generation = 0, timer
  async function refresh() {
    controller?.abort(); const version = ++generation
    const ids = [...new Set(userIds.value.filter(id => id && id !== '__all__').map(String))]
    if (!active.value || !ids.length) { statuses.value = {}; workStatuses.value = {}; loading.value = false; return }
    const current = new AbortController(), actor = localStorage.getItem('user_id')
    controller = current; loading.value = true
    try {
      const result = {}, schedules = {}
      for (let index = 0; index < ids.length; index += 200) {
        const data = await chatRequest('presence', { method: 'post', data: { userIds: ids.slice(index, index + 200) }, signal: current.signal })
        if (version !== generation || actor !== localStorage.getItem('user_id')) return
        for (const item of data.items) {
          result[item.userId] = item.desktopOnline
          schedules[item.userId] = item
        }
      }
      statuses.value = result
      workStatuses.value = schedules
    } catch { if (version === generation) { statuses.value = {}; workStatuses.value = {} } }
    finally { if (version === generation) loading.value = false }
  }
  watch(() => [active.value, userIds.value.join(',')], () => {
    clearInterval(timer); refresh()
    if (active.value) timer = setInterval(refresh, 15000)
  }, { immediate: true })
  const refreshActive = () => { if (active.value) void refresh() }
  const cleanups = [subscribe('connected', refreshActive), subscribe('foreground', refreshActive)]
  onBeforeUnmount(() => { ++generation; controller?.abort(); clearInterval(timer); cleanups.forEach(cleanup => cleanup()) })
  return { statuses, workStatuses, loading }
}
