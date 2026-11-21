// 路由守卫的会话权限同步：只有服务端明确拒绝（401/403）才视为未登录。
// 超时、网络中断、5xx、503 繁忙都属于临时故障，已有本地会话时放行并尽快重试，
// 避免局域网后端经公网访问数据库偶发变慢时，把用户误踢回登录页。
export function createSessionPermissionSync({
  fetchSession, apply, hasCachedSession,
  now = Date.now, ttlMs = 60_000, retryMs = 10_000,
}) {
  let syncedAt = 0, pending = null
  return function sync(force = false) {
    if (!force && now() - syncedAt < ttlMs) return Promise.resolve(true)
    // 快速连续跳转共用一次校验，不再叠加请求。
    if (pending) return pending
    const request = (async () => {
      try {
        apply(await fetchSession())
        syncedAt = now()
        return true
      } catch (error) {
        const status = error?.response?.status
        if (status === 401 || status === 403) return false
        if (!hasCachedSession()) return false
        syncedAt = now() - ttlMs + retryMs
        return true
      }
    })().finally(() => { if (pending === request) pending = null })
    pending = request
    return request
  }
}
