const optionCache = new Map()
const owner = () => typeof localStorage === 'undefined' ? '' : JSON.stringify(['user_id', 'user_permissions', 'user_roles'].map(key => localStorage.getItem(key)))
if (typeof window !== 'undefined') window.addEventListener('auth-session-clearing', () => invalidateOptionCache())

export const getCachedOptions = async (key, loader, { ttlMs = 60_000 } = {}) => {
  key = `${key}|${owner()}`
  const now = Date.now()
  const cached = optionCache.get(key)
  if (cached?.value && cached.expiresAt > now) return cached.value
  if (cached?.promise) return cached.promise

  const promise = Promise.resolve()
    .then(loader)
    .then((value) => {
      if (optionCache.get(key)?.promise === promise) optionCache.set(key, { value, expiresAt: Date.now() + ttlMs })
      return value
    })
    .catch((error) => {
      if (optionCache.get(key)?.promise === promise) optionCache.delete(key)
      throw error
    })
  optionCache.set(key, { promise, expiresAt: now + ttlMs })
  return promise
}

export const invalidateOptionCache = (prefix = '') => {
  for (const key of optionCache.keys()) {
    if (!prefix || key.startsWith(prefix)) optionCache.delete(key)
  }
}
