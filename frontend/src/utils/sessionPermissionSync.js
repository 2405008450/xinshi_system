// 会话失效和服务暂时不可用必须分开处理；权限未确认时取消导航。
export function createSessionPermissionSync({ getToken, fetchSession, applySession, now = Date.now }) {
  let syncedToken = null
  let syncedAt = 0
  let pending = null
  let pendingToken = null
  return async function sync(force = false) {
    const token = getToken()
    if (!token) return false
    if (!force && syncedToken === token && now() - syncedAt < 60_000) return true
    if (pending && pendingToken === token) return pending
    const request = (async () => {
      try {
        const session = await fetchSession()
        if (getToken() !== token) return null
        applySession(session)
        syncedToken = token
        syncedAt = now()
        return true
      } catch (error) {
        if (getToken() !== token) return null
        return error.response?.status === 401 ? false : null
      }
    })()
    pending = request
    pendingToken = token
    try { return await request }
    finally { if (pending === request) pending = null }
  }
}
