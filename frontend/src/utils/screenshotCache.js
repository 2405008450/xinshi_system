/**
 * 聊天与正文截图会话内内存 LRU 缓存与并发限流器。
 * 1. 按当前用户 + 图片 ID + 规格（thumb/original）隔离缓存，切群与滚动零重复拉取。
 * 2. 限制同时拉取并发数（默认 4，匹配后端 transfer_limit），避免进群瞬间打满连接。
 * 3. 登出/切换账号触发 auth-session-clearing 时自动清空并释放 ObjectURL。
 */

const DEFAULT_MAX_ENTRIES = 120
const DEFAULT_MAX_CONCURRENCY = 4

export function buildScreenshotCacheKey({ userId = '', id = '', variant = 'original', retainBlob = false } = {}) {
  return `${userId || 'anon'}:${id}:${variant || 'original'}${retainBlob ? ':blob' : ''}`
}

export function createScreenshotCache({
  maxEntries = DEFAULT_MAX_ENTRIES,
  maxConcurrency = DEFAULT_MAX_CONCURRENCY,
  createObjectURL = blob => URL.createObjectURL(blob),
  revokeObjectURL = url => URL.revokeObjectURL(url),
} = {}) {
  const entries = new Map()
  const inFlight = new Map()
  const queue = []
  let active = 0
  let epoch = 0

  function evictIfNeeded() {
    while (entries.size > maxEntries) {
      const oldestKey = entries.keys().next().value
      const oldest = entries.get(oldestKey)
      entries.delete(oldestKey)
      if (oldest?.url) {
        try { revokeObjectURL(oldest.url) } catch { /* 忽略已释放 URL */ }
      }
    }
  }

  function runNext() {
    while (active < maxConcurrency && queue.length > 0) {
      const task = queue.shift()
      active += 1
      Promise.resolve()
        .then(task.run)
        .then(task.resolve, task.reject)
        .finally(() => {
          active -= 1
          runNext()
        })
    }
  }

  function enqueue(run) {
    return new Promise((resolve, reject) => {
      queue.push({ run, resolve, reject })
      runNext()
    })
  }

  function get(key) {
    const existing = entries.get(key)
    if (!existing) return null
    entries.delete(key)
    entries.set(key, existing)
    return existing
  }

  function fetch(key, loader, { retainBlob = false } = {}) {
    const cached = get(key)
    if (cached) return Promise.resolve(cached)
    const pending = inFlight.get(key)
    if (pending) return pending

    const currentEpoch = epoch
    const promise = enqueue(async () => {
      const blob = await loader()
      const url = createObjectURL(blob)
      const record = {
        url,
        type: blob?.type || '',
        blob: retainBlob ? blob : undefined,
      }
      if (currentEpoch !== epoch) {
        try { revokeObjectURL(url) } catch { /* 会话已切换，立即释放 */ }
        return record
      }
      const prev = entries.get(key)
      if (prev?.url && prev.url !== url) {
        try { revokeObjectURL(prev.url) } catch { /* 忽略 */ }
      }
      entries.delete(key)
      entries.set(key, record)
      evictIfNeeded()
      return record
    }).finally(() => {
      if (inFlight.get(key) === promise) inFlight.delete(key)
    })

    inFlight.set(key, promise)
    return promise
  }

  function clear() {
    epoch += 1
    for (const item of entries.values()) {
      if (item?.url) {
        try { revokeObjectURL(item.url) } catch { /* 忽略 */ }
      }
    }
    entries.clear()
    inFlight.clear()
  }

  return {
    get,
    fetch,
    clear,
    size: () => entries.size,
  }
}

export const screenshotCache = createScreenshotCache()

export function clearScreenshotCache() {
  screenshotCache.clear()
}

if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
  window.addEventListener('auth-session-clearing', clearScreenshotCache)
}
