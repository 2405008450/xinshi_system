// 兜底轮询调度：实时推送是主通道，轮询只补偿推送不可达的情况（例如局域网与云端后端互不同步）。
// 页面可见时按 visibleMs 轮询；隐藏时按 hiddenMs 放慢（null 表示完全暂停）；恢复可见时补查一次。
// minGapMs 内的重复触发（focus 与 visibilitychange 同时到达等）只执行一次，避免跳转时叠加请求。
export function createVisiblePolling({
  task, visibleMs, hiddenMs = null, minGapMs = 15000,
  now = Date.now,
  target = globalThis.document,
  isVisible = () => target?.visibilityState !== 'hidden',
  setTimer = globalThis.setTimeout,
  clearTimer = globalThis.clearTimeout,
}) {
  let timer = null, running = false, last = 0, active = false
  const delay = () => (isVisible() ? visibleMs : hiddenMs)
  function schedule() {
    clearTimer(timer); timer = null
    if (!active) return
    const ms = delay()
    if (ms == null) return
    timer = setTimer(tick, ms)
  }
  async function run(force) {
    if (running) return
    if (!force && last && now() - last < minGapMs) return
    running = true; last = now()
    try { await task() } catch { /* 下一轮继续 */ } finally { running = false }
  }
  async function tick() { timer = null; if (!active) return; await run(true); schedule() }
  const onVisibility = () => {
    if (!active) return
    if (isVisible()) void run(false)
    schedule()
  }
  return {
    start({ immediate = false } = {}) {
      if (active) return
      active = true
      target?.addEventListener?.('visibilitychange', onVisibility)
      if (immediate) void run(true)
      schedule()
    },
    stop() {
      active = false; clearTimer(timer); timer = null
      target?.removeEventListener?.('visibilitychange', onVisibility)
    },
    // force=true 用于实时事件，必须立即刷新；否则受 minGapMs 合并。
    trigger(force = false) { return run(force) },
  }
}
