import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useChatMentions } from './useChatMentions'

// 会话仍按项目计数；这里单独维护一个项目内的消息游标。
export function useProjectMentionNavigation(locate, cancelLocate) {
  const project = ref(null)
  const selectedId = ref('')
  const locating = ref(false)
  const notice = ref('')
  let selectionVersion = 0
  const filters = computed(() => ({ projectType: project.value?.projectType, projectId: project.value?.projectId }))
  const query = useChatMentions(ref(''), computed(() => !!project.value), filters, selectedId)
  const index = computed(() => query.items.value.findIndex(item => item.messageId === selectedId.value))
  const model = reactive({ project, selectedId, locating, notice, index, ...query })

  function close() {
    ++selectionVersion
    cancelLocate?.(project.value?.key)
    selectedId.value = ''; locating.value = false; notice.value = ''; project.value = null
  }
  function browse(session) {
    if (project.value?.key === session.key) return
    close()
    project.value = session
  }
  async function select(item) {
    if (item.key !== project.value?.key) return
    const version = ++selectionVersion
    selectedId.value = item.messageId
    notice.value = ''; locating.value = true
    try {
      const ok = await locate(item)
      if (version !== selectionVersion) return
      if (!ok) {
        notice.value = '无法定位这条消息，请刷新列表后重试'
        await query.refresh()
      }
    } catch {
      if (version === selectionVersion) {
        notice.value = '定位失败，请重试或重新选择消息'
        await query.refresh()
      }
    } finally {
      if (version === selectionVersion) locating.value = false
    }
  }
  async function move(direction) {
    if (query.loading.value || index.value < 0) return
    const version = selectionVersion
    const target = index.value + direction
    if (target >= query.items.value.length && query.hasMore.value) await query.loadMore()
    if (version !== selectionVersion) return
    const item = query.items.value[target]
    if (item) await select(item)
  }
  async function latest(session) {
    browse(session)
    const version = selectionVersion
    await nextTick()
    // 首次操作才加载历史；显式等待加载结束，不能以会话目录数量代替消息游标。
    if (query.loading.value) await new Promise(resolve => {
      const stop = watch(query.loading, loading => { if (!loading) { stop(); resolve() } })
    })
    if (version !== selectionVersion || query.error.value) return
    const item = query.items.value[0]
    if (item) await select(item)
  }
  watch([query.loading, query.items], () => {
    if (!query.loading.value && !query.error.value && selectedId.value && index.value < 0) {
      ++selectionVersion
      cancelLocate?.(project.value?.key)
      selectedId.value = ''; locating.value = false
      notice.value = '这条提及已撤回或不可查看，请重新选择消息'
    }
  })
  onBeforeUnmount(close)
  return { model, browse, select, move, close, latest }
}
