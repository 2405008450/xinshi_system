import { onBeforeUnmount, ref, watch } from 'vue'
import { businessDateTimeInputValue } from '../utils/dateTime.js'

const TTL = 7 * 24 * 3600000
const clone = value => JSON.parse(JSON.stringify(value))

// Blob 地址仅在当前页面有效；恢复图片时按图片 ID 重新获取授权内容。
export function normalizeMailDraftFields(fields) {
  return JSON.parse(JSON.stringify(fields, (_key, value) => typeof value === 'string'
    ? value.replace(/<img\b[^>]*>/gi, tag => tag.replace(/\bsrc=(['"])[\s\S]*?\1/i, 'src=""'))
    : value))
}

export function createMailDraftStore({ storage = () => globalThis.localStorage, user = () => storage()?.getItem('user_id'), now = Date.now } = {}) {
  const storageKey = () => {
    try { const id = user(); return id ? `mail-drafts:${id}` : '' } catch { return '' }
  }
  const write = (key, drafts) => {
    if (!key) return
    try {
      if (Object.keys(drafts).length) storage().setItem(key, JSON.stringify(drafts))
      else storage().removeItem(key)
    } catch { /* 禁用存储或空间不足时不阻断编辑与发送。 */ }
  }
  const read = (key) => {
    if (!key) return {}
    try {
      const parsed = JSON.parse(storage().getItem(key) || '{}')
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('invalid')
      const valid = Object.fromEntries(Object.entries(parsed).filter(([, entry]) => {
        const age = now() - Date.parse(entry?.savedAt)
        return entry?.fields && typeof entry.fields === 'object' && !Array.isArray(entry.fields)
          && Number.isFinite(age) && age >= 0 && age < TTL
      }).sort((a, b) => Date.parse(b[1].savedAt) - Date.parse(a[1].savedAt)).slice(0, 30))
      write(key, valid)
      return valid
    } catch { write(key, {}); return {} }
  }
  return {
    storageKey,
    restore(key) { return clone(read(storageKey())[key] || null) },
    save(key, fields, baseline, owner = storageKey()) {
      // 账号切换后，旧编辑器不得把内容写入新账号。
      if (!owner || owner !== storageKey()) return
      let drafts = read(owner)
      const normalized = normalizeMailDraftFields(fields)
      const defaults = normalizeMailDraftFields(baseline)
      const changed = Object.fromEntries(Object.entries(normalized).filter(([field, value]) =>
        JSON.stringify(value) !== JSON.stringify(defaults[field])))
      if (!Object.keys(changed).length) delete drafts[key]
      else if (JSON.stringify(drafts[key]?.fields) !== JSON.stringify(changed)) {
        // 同秒保存时也优先保留最新编辑的一条，避免达到条数上限后丢失新草稿。
        delete drafts[key]
        drafts = { [key]: { fields: changed, savedAt: `${businessDateTimeInputValue(now()).replace(' ', 'T')}+08:00` }, ...drafts }
      }
      const limited = Object.fromEntries(Object.entries(drafts)
        .sort((a, b) => Date.parse(b[1].savedAt) - Date.parse(a[1].savedAt)).slice(0, 30))
      write(owner, limited)
    },
    clear(key) { const owner = storageKey(); const drafts = read(owner); delete drafts[key]; write(owner, drafts) },
  }
}

export function useMailDraftCache() {
  const store = createMailDraftStore()
  const restoredAt = ref('')
  let active = null
  let timer = null
  let stop = null
  const flush = () => {
    clearTimeout(timer)
    timer = null
    if (active) store.save(active.key, active.getFields(), active.baseline, active.owner)
  }
  const pause = () => {
    flush()
    stop?.()
    stop = null
    active = null
    restoredAt.value = ''
  }
  const track = (key, getFields, baselineFields) => {
    pause()
    active = { key, getFields, baseline: clone(baselineFields), owner: store.storageKey() }
    let draft = store.restore(key)
    if (draft) {
      draft.fields = Object.fromEntries(Object.entries(draft.fields).filter(([field, value]) => {
        if (!(field in baselineFields)) return false
        if (Array.isArray(baselineFields[field])) return Array.isArray(value)
          && value.every(item => item && typeof item === 'object' && typeof item.id === 'string')
        return typeof value === typeof baselineFields[field]
      }))
      if (!Object.keys(draft.fields).length) { store.clear(key); draft = null }
    }
    restoredAt.value = draft?.savedAt || ''
    stop = watch(getFields, () => {
      clearTimeout(timer)
      timer = setTimeout(flush, 400)
    }, { deep: true, flush: 'sync' })
    return draft
  }
  const clear = () => {
    const key = active?.key
    const owner = active?.owner
    clearTimeout(timer)
    timer = null
    stop?.()
    stop = null
    active = null
    restoredAt.value = ''
    if (key && owner === store.storageKey()) store.clear(key)
  }
  const unload = () => flush()
  globalThis.window?.addEventListener('pagehide', unload)
  globalThis.window?.addEventListener('beforeunload', unload)
  onBeforeUnmount(() => {
    pause()
    globalThis.window?.removeEventListener('pagehide', unload)
    globalThis.window?.removeEventListener('beforeunload', unload)
  })
  return { restore: store.restore, track, flush, pause, clear, restoredAt }
}
