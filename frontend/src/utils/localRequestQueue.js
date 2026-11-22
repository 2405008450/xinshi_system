// 本机通过公网访问数据库，多个 localhost 标签页共享少量连接。
// 排队发生在发送请求之前，避免后台轮询挤满后端或消耗 HTTP 超时时间。
function retryDelay(milliseconds, signal, canceledError, config) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(canceledError(config)); return }
    const cleanup = () => signal?.removeEventListener('abort', abort)
    const timer = setTimeout(() => { cleanup(); resolve() }, milliseconds)
    const abort = () => { clearTimeout(timer); cleanup(); reject(canceledError(config)) }
    signal?.addEventListener('abort', abort, { once: true })
  })
}

export function createLocalRequestQueue({ locks, hostname, canceledError, slots = 2, pause = retryDelay }) {
  let nextSlot = 0
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(hostname)
  return async (config, send) => {
    if (!local) return send(config)
    const sendRead = async () => {
      for (let attempt = 0; ; attempt++) {
        try { return await send(config) }
        catch (error) {
          const headers = error.response?.headers
          const retryAfter = Number(headers?.get?.('retry-after') ?? headers?.['retry-after'])
          if (String(config.method || 'get').toLowerCase() !== 'get' || error.response?.status !== 503 ||
              !(retryAfter > 0) || attempt >= 2 || config.signal?.aborted) throw error
          await pause(Math.min(retryAfter, 2) * 1000, config.signal, canceledError, config)
        }
      }
    }
    if (!locks?.request) return sendRead()
    if (config.signal?.aborted) throw canceledError(config)
    const auth = /^\/?auth\//.test(config.url || '')
    const name = auth ? 'xinshi-local-api-auth' : `xinshi-local-api-${nextSlot++ % slots}`
    try {
      return await locks.request(name, { mode: 'exclusive', ...(config.signal ? { signal: config.signal } : {}) }, () => {
        if (config.signal?.aborted) throw canceledError(config)
        return sendRead()
      })
    } catch (error) {
      if (error.name === 'AbortError') throw canceledError(config)
      throw error
    }
  }
}
