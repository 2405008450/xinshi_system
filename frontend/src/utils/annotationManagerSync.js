const eventName = 'annotation-project-managers-updated'
const storageKey = 'xinshi.annotationManagersChanged'

export function notifyAnnotationManagersUpdated(projectId) {
  const detail = { projectId: String(projectId), nonce: Date.now() }
  window.dispatchEvent(new CustomEvent(eventName, { detail }))
  try { localStorage.setItem(storageKey, JSON.stringify(detail)) } catch { /* 当前页面仍正常刷新。 */ }
}

export function subscribeAnnotationManagersUpdated(callback) {
  const local = event => { if (event.detail?.projectId) callback(event.detail.projectId) }
  const remote = event => {
    if (event.key !== storageKey || !event.newValue) return
    try { const detail = JSON.parse(event.newValue); if (detail.projectId) callback(detail.projectId) } catch { /* 忽略无效同步信号。 */ }
  }
  window.addEventListener(eventName, local)
  window.addEventListener('storage', remote)
  return () => { window.removeEventListener(eventName, local); window.removeEventListener('storage', remote) }
}
