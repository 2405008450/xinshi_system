export const createIdempotencyKey = () => (
  globalThis.crypto?.randomUUID?.()
  || `${Date.now()}-${Math.random().toString(16).slice(2)}`
)

export const createRequestUuid = () => {
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}

export const resolveIdempotencyKey = (state, payload, providedKey = '') => {
  if (providedKey) return providedKey
  const signature = JSON.stringify(payload)
  if (!state.key || state.signature !== signature) {
    state.key = createIdempotencyKey()
    state.signature = signature
  }
  return state.key
}

export const clearIdempotencyKey = (state, key) => {
  if (state.key === key) {
    state.key = ''
    state.signature = ''
  }
}

export const resetIdempotencyKey = (state) => {
  state.key = ''
  state.signature = ''
}
