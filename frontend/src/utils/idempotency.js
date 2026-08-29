export const createIdempotencyKey = () => (
  globalThis.crypto?.randomUUID?.()
  || `${Date.now()}-${Math.random().toString(16).slice(2)}`
)

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
