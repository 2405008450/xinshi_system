import { getWorkbenchFilterStorageKey } from './workbenchList.js'

export function watchAuthSession(browser = window) {
  const { localStorage: storage, location } = browser
  let token = storage.getItem('token')
  const leaveProtectedPage = (currentToken, flushDrafts) => {
    if (location.pathname === '/login') return
    if (flushDrafts) browser.dispatchEvent(new Event('auth-session-clearing'))
    if (currentToken) location.reload()
    else location.replace('/login')
  }
  const onStorage = (event) => {
    if (event.storageArea !== storage || (event.key !== 'token' && event.key !== null)) return
    const currentToken = storage.getItem('token')
    const previousToken = event.key === 'token' ? event.oldValue : token
    const changed = previousToken && currentToken !== previousToken
    token = currentToken
    if (changed) leaveProtectedPage(currentToken, true)
  }
  const onPageShow = (event) => {
    if (event.persisted) leaveProtectedPage(storage.getItem('token'))
  }
  browser.addEventListener('storage', onStorage)
  browser.addEventListener('pageshow', onPageShow)
  return () => {
    browser.removeEventListener('storage', onStorage)
    browser.removeEventListener('pageshow', onPageShow)
  }
}

// 登录信息和旧版工作台筛选随会话清除，保留草稿与个人偏好。
export function clearAuthSession(storage = localStorage) {
  if (typeof window !== 'undefined' && storage === window.localStorage) window.dispatchEvent(new Event('auth-session-clearing'))
  if (storage.getItem) {
    const userId = storage.getItem('user_id')
    const userName = storage.getItem('user_name')
    for (const scope of ['my-tasks', 'management-projects']) {
      storage.removeItem(getWorkbenchFilterStorageKey(scope, userId, userName))
    }
  }
  for (const key of ['token', 'user_roles', 'user_permissions', 'user_name', 'user_id', 'user_full_name']) {
    storage.removeItem(key)
  }
}
