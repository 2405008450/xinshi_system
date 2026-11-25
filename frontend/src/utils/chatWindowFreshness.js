// 已打开的会话保留自己的数据，短时间切回来时复用。
export const CHAT_WINDOW_REFRESH_MS = 15000
export const CHAT_MEMBERS_REFRESH_MS = 60000

export function createChatWindowFreshness(maxAgeMs, now = () => performance.now()) {
  let updatedAt = -Infinity
  let revision = 0
  return {
    isStale: () => now() - updatedAt >= maxAgeMs,
    invalidate() {
      ++revision
      updatedAt = -Infinity
    },
    begin() {
      const current = ++revision
      return () => {
        if (current === revision) updatedAt = now()
      }
    },
  }
}
