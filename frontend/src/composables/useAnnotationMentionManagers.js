import { onBeforeUnmount, ref, watch } from 'vue'
import { getAnnotationProject } from '@/api/annotationProjects'
import { subscribeAnnotationManagersUpdated } from '@/utils/annotationManagerSync'

export function useAnnotationMentionManagers(projectId, enabled) {
  const project = ref(null)
  let controller, generation = 0, disposed = false
  async function load() {
    controller?.abort(); const version = ++generation
    if (!enabled.value || !projectId.value || disposed) return
    const current = new AbortController(); controller = current
    try {
      const value = await getAnnotationProject(projectId.value, { signal: current.signal })
      if (!disposed && version === generation) project.value = value
    } catch { if (version === generation) project.value = null }
  }
  watch(projectId, () => { project.value = null })
  watch(() => [projectId.value, enabled.value], load, { immediate: true })
  const unsubscribe = subscribeAnnotationManagersUpdated(id => {
    if (String(id) === String(projectId.value)) { project.value = null; void load() }
  })
  onBeforeUnmount(() => { disposed = true; ++generation; controller?.abort(); unsubscribe() })
  return project
}
