import { getWorkbenchFilterStorageKey } from './workbenchList.js'

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
