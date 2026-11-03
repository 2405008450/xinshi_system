import { nextTick, onBeforeUnmount, watch } from 'vue'

// 持续跟随最新消息，覆盖图片异步加载、编辑器展开及窗口大小变化。
export function useChatAutoScroll(getViewport, isActive) {
  let viewport, resizeObserver, following = true, lastTop = 0
  const scrollToBottom = () => {
    following = true
    if (!viewport || !isActive() || !viewport.clientHeight) return
    viewport.scrollTop = viewport.scrollHeight
    lastTop = viewport.scrollTop
  }
  const pause = () => { following = false }
  const onScroll = () => {
    if (!isActive()) return
    const top = viewport.scrollTop
    const gap = viewport.scrollHeight - top - viewport.clientHeight
    // 高度变化产生的滚动事件不能取消跟随；用户向上滚动才暂停。
    if (top < lastTop && gap >= 4) following = false
    else if (top > lastTop && gap < 4) following = true
    lastTop = top
  }
  const disconnect = () => {
    resizeObserver?.disconnect()
    viewport?.removeEventListener('scroll', onScroll)
  }
  watch(getViewport, element => {
    disconnect()
    viewport = element
    if (!viewport) return
    lastTop = viewport.scrollTop
    viewport.addEventListener('scroll', onScroll, { passive: true })
    resizeObserver = new ResizeObserver(() => {
      if (following) scrollToBottom()
    })
    resizeObserver.observe(viewport)
    if (viewport.firstElementChild) resizeObserver.observe(viewport.firstElementChild)
  }, { immediate: true, flush: 'post' })
  onBeforeUnmount(disconnect)
  return {
    pause,
    bottom: async () => { following = true; await nextTick(); scrollToBottom() },
  }
}
