/**
 * 聊天消息精准定位滚动器：
 * 1. 基于容器与目标元素的实时几何坐标（getBoundingClientRect）计算居中 scrollTop，
 *    避免 scrollIntoView({ behavior: 'smooth' }) 在非 100% 缩放、跨浏览器动画和外层容器上的偏移；
 * 2. 在定位后的短暂稳定期内持续监听容器/内容尺寸变化及图片解码完成事件，
 *    若上方异步图片或首帧布局回流把目标消息顶偏超过 2px，自动静默重新对齐；
 * 3. 一旦用户主动滚轮、触摸、拖拽滚动条或按键翻页，立即交还控制权，不与用户抢滚动条。
 */

export function computeCenteredScrollTop(container, target, { topPadding = 16 } = {}) {
  if (!container || !target) return null
  const containerRect = container.getBoundingClientRect?.()
  const targetRect = target.getBoundingClientRect?.()
  if (!containerRect || !targetRect || !containerRect.height) return null
  const computedPadding = typeof getComputedStyle === 'function'
    ? Number.parseFloat(getComputedStyle(container)?.scrollPaddingTop) || 0
    : 0
  const effectiveTopPadding = Math.max(topPadding, computedPadding)
  const maxTop = Math.max(0, (container.scrollHeight || 0) - (container.clientHeight || 0))
  const desiredOffset = targetRect.height >= containerRect.height - effectiveTopPadding * 2
    ? effectiveTopPadding
    : (containerRect.height - targetRect.height) / 2
  const rawTop = (container.scrollTop || 0) + (targetRect.top - containerRect.top) - desiredOffset
  return Math.max(0, Math.min(maxTop, Math.round(rawTop)))
}

export function createChatMessageScroller({
  settleMs = 1400,
  tolerancePx = 2,
  topPadding = 16,
  onLockChange = null,
} = {}) {
  let active = false
  let cleanupFns = []
  let settleTimer = 0
  let rafIds = []
  let runId = 0

  function setLocked(next) {
    if (active === next) return
    active = next
    onLockChange?.(next)
  }

  function stop() {
    ++runId
    if (settleTimer) {
      clearTimeout(settleTimer)
      settleTimer = 0
    }
    if (typeof cancelAnimationFrame === 'function') {
      for (const id of rafIds) cancelAnimationFrame(id)
    }
    rafIds = []
    for (const fn of cleanupFns) {
      try { fn() } catch { /* 清理失败不影响后续定位。 */ }
    }
    cleanupFns = []
    setLocked(false)
  }

  function scrollTo(getContainer, getTarget, options = {}) {
    stop()
    const currentRun = runId
    const duration = Number.isFinite(options.settleMs) ? options.settleMs : settleMs
    const tolerance = Number.isFinite(options.tolerancePx) ? options.tolerancePx : tolerancePx
    const padding = Number.isFinite(options.topPadding) ? options.topPadding : topPadding

    const container = typeof getContainer === 'function' ? getContainer() : getContainer
    const target = typeof getTarget === 'function' ? getTarget() : getTarget
    if (!container || !target) return false

    const align = () => {
      if (currentRun !== runId) return false
      const c = typeof getContainer === 'function' ? getContainer() : container
      const t = typeof getTarget === 'function' ? getTarget() : target
      if (!c || !t || (t.isConnected === false)) return false
      const nextTop = computeCenteredScrollTop(c, t, { topPadding: padding })
      if (nextTop === null) return false
      if (Math.abs((c.scrollTop || 0) - nextTop) > tolerance || !active) {
        c.scrollTop = nextTop
      }
      return true
    }

    setLocked(true)
    align()

    // 覆盖后台窗口恢复、侧栏切换或样式重排后的首两帧布局稳定。
    if (typeof requestAnimationFrame === 'function') {
      const id1 = requestAnimationFrame(() => {
        if (currentRun !== runId) return
        align()
        const id2 = requestAnimationFrame(() => {
          if (currentRun !== runId) return
          align()
        })
        rafIds.push(id2)
      })
      rafIds.push(id1)
    }

    const onUserInterrupt = () => {
      if (currentRun === runId) stop()
    }
    const onKeyInterrupt = (event) => {
      if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event?.key)) {
        onUserInterrupt()
      }
    }

    if (typeof container.addEventListener === 'function') {
      const userEvents = ['wheel', 'pointerdown', 'touchstart']
      for (const evt of userEvents) {
        container.addEventListener(evt, onUserInterrupt, { passive: true })
        cleanupFns.push(() => container.removeEventListener(evt, onUserInterrupt))
      }
      container.addEventListener('keydown', onKeyInterrupt)
      cleanupFns.push(() => container.removeEventListener('keydown', onKeyInterrupt))

      const onMediaLoad = () => {
        if (currentRun === runId) align()
      }
      container.addEventListener('load', onMediaLoad, true)
      cleanupFns.push(() => container.removeEventListener('load', onMediaLoad, true))
    }

    if (typeof ResizeObserver === 'function') {
      const observer = new ResizeObserver(() => {
        if (currentRun === runId) align()
      })
      try {
        observer.observe(container)
        if (container.firstElementChild) observer.observe(container.firstElementChild)
      } catch { /* 测试环境非真实 DOM 节点时忽略。 */ }
      cleanupFns.push(() => observer.disconnect())
    }

    if (duration > 0) {
      settleTimer = setTimeout(() => {
        if (currentRun === runId) stop()
      }, duration)
    }
    return true
  }

  return {
    scrollTo,
    stop,
    isLocating: () => active,
  }
}
