const optionCache = new Map()

export const getCachedOptions = async (key, loader, { ttlMs = 60_000 } = {}) => {
  const now = Date.now()
  const cached = optionCache.get(key)
  if (cached?.value && cached.expiresAt > now) return cached.value
  if (cached?.promise) return cached.promise

  const promise = Promise.resolve()
    .then(loader)
    .then((value) => {
      optionCache.set(key, { value, expiresAt: Date.now() + ttlMs })
      return value
    })
    .catch((error) => {
      optionCache.delete(key)
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
