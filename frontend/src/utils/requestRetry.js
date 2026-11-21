// 幂等 GET 的一次自动重试：只处理“服务暂时繁忙/网关刚好断开”的瞬时故障。
// 不重试超时（已等待完整超时时间，再试只会叠加后端负载）、写请求、被取消的请求和文件下载。
const RETRYABLE_STATUS = new Set([502, 503])
const MIN_DELAY_MS = 300
const MAX_DELAY_MS = 3000
const DEFAULT_DELAY_MS = 800

export function retryDelayMs(error) {
  const config = error?.config
  if (!config || error?.code === 'ERR_CANCELED' || config.signal?.aborted) return null
  if (!['get', 'head'].includes(String(config.method || 'get').toLowerCase())) return null
  if (config.retry === false || (config.__retryCount || 0) >= 1) return null
  if (config.responseType === 'blob' || config.responseType === 'arraybuffer' || config.responseType === 'stream') return null
  const response = error.response
  if (!response) return error.code === 'ERR_NETWORK' ? DEFAULT_DELAY_MS : null
  if (!RETRYABLE_STATUS.has(response.status)) return null
  const header = response.headers?.['retry-after']
  const seconds = Number(Array.isArray(header) ? header[0] : header)
  const delay = Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : DEFAULT_DELAY_MS
  return Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, delay))
}

export const withRetryMark = config => ({ ...config, __retryCount: (config.__retryCount || 0) + 1 })
