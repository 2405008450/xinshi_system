// 只清理当前登录信息，保留按用户隔离的字段设置等个人偏好。
export function clearAuthSession(storage = localStorage) {
  if (typeof window !== 'undefined' && storage === window.localStorage) window.dispatchEvent(new Event('auth-session-clearing'))
  for (const key of ['token', 'user_roles', 'user_permissions', 'user_name', 'user_id', 'user_full_name']) {
    storage.removeItem(key)
  }
}
