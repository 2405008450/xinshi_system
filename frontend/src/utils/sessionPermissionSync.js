// 已有会话遇到临时故障时沿用同一令牌的本地权限，换号后重新确认。
export function createSessionPermissionSync({
  getToken, fetchSession, apply, hasCachedSession,
  now = Date.now, ttlMs = 60_000, retryMs = 10_000,
}) {
  let cachedToken = getToken()
  let syncedToken = null, syncedAt = 0
  let pending = null, pendingToken = null

  return function sync(force = false) {
    const token = getToken()
    if (!token) return Promise.resolve(false)
    if (!force && syncedToken === token && now() - syncedAt < ttlMs) return Promise.resolve(true)
    if (pending && pendingToken === token) return pending
    const request = (async () => {
      try {
        const session = await fetchSession()
        if (getToken() !== token) return null
        apply(session)
        cachedToken = syncedToken = token
        syncedAt = now()
        return true
      } catch (error) {
        const status = error?.response?.status
        const currentToken = getToken()
        if (currentToken !== token) return status === 401 && !currentToken ? false : null
        if (status === 401 || status === 403) {
          cachedToken = syncedToken = null
          return false
        }
        if (cachedToken !== token || !hasCachedSession()) return null
        syncedToken = token
        syncedAt = now() - ttlMs + retryMs
        return true
      }
    })().finally(() => { if (pending === request) pending = null })
    pending = request
    pendingToken = token
    return request
  }
}
