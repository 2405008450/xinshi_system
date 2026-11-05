// 合并突发事件，限制刷新频率；请求执行期间只保留一次后续刷新。
export function createCoalescedRefresh(run, {
  debounceMs = 400, minIntervalMs = 3000,
  visible = () => true, now = () => performance.now(),
  setTimer = setTimeout, clearTimer = clearTimeout,
} = {}) {
  let timer = null
  let running = false
  let dirty = false
  let stopped = false
  let lastStarted = -Infinity
  let waiters = []

  function schedule({ immediate = false } = {}) {
    if (stopped || !visible()) return Promise.resolve()
    const completion = new Promise(resolve => waiters.push(resolve))
    dirty = true
    if (running || timer !== null) return completion
    const delay = Math.max(immediate ? 0 : debounceMs, minIntervalMs - (now() - lastStarted))
    timer = setTimer(async () => {
      timer = null
      const currentWaiters = waiters
      waiters = []
      if (stopped || !visible()) { dirty = false; currentWaiters.forEach(resolve => resolve()); return }
      dirty = false
      running = true
      lastStarted = now()
      try { await run() } finally {
        running = false
        currentWaiters.forEach(resolve => resolve())
        if (dirty && !stopped) schedule()
      }
    }, Math.max(0, delay))
    return completion
  }

  function stop() {
    stopped = true
    dirty = false
    if (timer !== null) clearTimer(timer)
    timer = null
    waiters.forEach(resolve => resolve())
    waiters = []
  }
  return { schedule, stop }
}
