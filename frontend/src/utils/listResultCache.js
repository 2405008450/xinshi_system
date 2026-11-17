// 仅缓存当前会话的展示结果；命中后仍请求最新数据。
const entries = new Map()
let generation = 0
let activeOwner = null
const scope = () => JSON.stringify(['user_id', 'user_permissions', 'user_roles'].map(key => localStorage.getItem(key)))
const stable = value => Array.isArray(value) ? value.map(stable) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])])) : value
export function clearListResults() { generation++; entries.clear() }
export function listResultTicket(module, params = {}) {
  const owner = scope()
  if (activeOwner !== owner) { clearListResults(); activeOwner = owner }
  const version = generation
  const key = JSON.stringify([owner, module, stable(params)])
  return {
    read() {
      const entry = entries.get(key)
      if (!entry || Date.now() - entry.at > 600000 || owner !== scope() || version !== generation) return null
      entries.delete(key); entries.set(key, entry)
      return JSON.parse(entry.value)
    },
    write(value) {
      if (owner !== scope() || version !== generation) return
      entries.delete(key); entries.set(key, {at: Date.now(), value: JSON.stringify(value)})
      while (entries.size > 20) entries.delete(entries.keys().next().value)
    },
  }
}
if (typeof window !== 'undefined') window.addEventListener('auth-session-clearing', clearListResults)
