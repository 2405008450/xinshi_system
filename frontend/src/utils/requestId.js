// 请求去重标识，不用于令牌、密码或其他安全凭据。
export const isRequestId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)

export function createRequestId(cryptoApi = globalThis.crypto) {
  try {
    const value = cryptoApi?.randomUUID?.()
    if (isRequestId(value)) return value
  } catch { /* 部分浏览器暴露方法但调用失败，继续使用兼容实现。 */ }
  const bytes = new Uint8Array(16)
  try {
    if (!cryptoApi?.getRandomValues) throw new Error('unavailable')
    cryptoApi.getRandomValues(bytes)
  } catch {
    // 旧浏览器最后兜底；只用于避免业务重复提交。
    for (let index = 0; index < bytes.length; index++) bytes[index] = Math.floor(Math.random() * 256)
  }
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export const ensureRequestId = value => isRequestId(value) ? value : createRequestId()
