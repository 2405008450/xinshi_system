const PREFERENCE_PREFIX = 'desktop_notifications_enabled'
const GUIDE_PREFIX = 'desktop_notifications_guide_seen'

const getCurrentUserKey = () => {
  try {
    return localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
  } catch {
    return 'anonymous'
  }
}

const getStorageKey = (prefix) => `${prefix}:${getCurrentUserKey()}`

const readBoolean = (key) => {
  try {
    return localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

const writeBoolean = (key, value) => {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // 存储不可用时仍以浏览器权限为准，不中断通知功能。
  }
}

export const getDesktopNotificationState = () => {
  const supported = typeof window !== 'undefined' && 'Notification' in window
  const secure = typeof window !== 'undefined' && window.isSecureContext
  const permission = supported ? window.Notification.permission : 'unsupported'
  const preferred = readBoolean(getStorageKey(PREFERENCE_PREFIX))

  return {
    supported,
    secure,
    permission,
    enabled: supported && secure && permission === 'granted' && preferred,
  }
}

export const enableDesktopNotifications = async () => {
  const state = getDesktopNotificationState()
  if (!state.supported || !state.secure) return getDesktopNotificationState()

  const permission = state.permission === 'granted'
    ? 'granted'
    : await window.Notification.requestPermission()

  writeBoolean(getStorageKey(PREFERENCE_PREFIX), permission === 'granted')
  return getDesktopNotificationState()
}

export const disableDesktopNotifications = () => {
  writeBoolean(getStorageKey(PREFERENCE_PREFIX), false)
  return getDesktopNotificationState()
}

export const hasSeenDesktopNotificationGuide = () => readBoolean(getStorageKey(GUIDE_PREFIX))

export const markDesktopNotificationGuideSeen = () => {
  writeBoolean(getStorageKey(GUIDE_PREFIX), true)
}

/**
 * 展示操作系统通知。返回 false 时调用方应回退到站内浮层通知。
 */
export const showDesktopNotification = (notification, onClick) => {
  if (!getDesktopNotificationState().enabled) return false

  try {
    const desktopNotification = new window.Notification(notification.title || '新通知', {
      body: notification.content || '',
      icon: '/favicon.svg',
      tag: notification.id ? `xinshi-notification-${notification.id}` : undefined,
    })

    desktopNotification.onclick = (event) => {
      event.preventDefault()
      window.focus()
      desktopNotification.close()
      Promise.resolve(onClick?.()).catch((error) => {
        console.error('处理桌面通知点击失败', error)
      })
    }
    return true
  } catch (error) {
    console.error('展示桌面通知失败', error)
    return false
  }
}
