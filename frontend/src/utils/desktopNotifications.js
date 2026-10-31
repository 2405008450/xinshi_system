import { notificationAcknowledgements } from './notificationAcknowledgements.js'

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
export const showDesktopNotification = async (notification, onClick) => {
  if (notificationAcknowledgements.has(notification.id)) return true
  if (!getDesktopNotificationState().enabled) return false

  // 检查是否支持 Service Worker
  if (!('serviceWorker' in navigator)) {
    console.warn('当前浏览器不支持 Service Worker 通知')
    return false
  }

  try {
    const reg = await navigator.serviceWorker.ready
    const tag = notification.id ? `xinshi-notification-${notification.id}` : undefined

    // 1. 使用 Service Worker 展示通知
    await reg.showNotification(notification.title || '新通知', {
      body: notification.content || '',
      icon: '/favicon.svg',
      tag: tag,
      // 👇 关键：把通知 ID 和需要跳转的 URL 传给 sw.js，以便点击时处理
      data: {
        notificationId: notification.id,
        url: onClick ? window.location.href : '/' // 如果有点击回调，默认跳转当前页；否则跳首页
      }
    })

    // 2. 处理“取消订阅（关闭）”逻辑
    // 注意：showNotification 返回的不是实例。如果我们想在前端主动关闭它，只能通过 getNotifications 找到它
    const unsubscribe = notificationAcknowledgements.subscribe(async id => {
      if (id === String(notification.id)) {
        unsubscribe()
        if (tag) {
          const notifications = await reg.getNotifications({ tag })
          notifications.forEach(n => n.close())
        }
      }
    })

    // 3. 处理点击逻辑（必须在 sw.js 中监听，这里使用 postMessage 通知前端）
    // 当用户点击通知时，sw.js 会通过 postMessage 发消息回来，监听它即可
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data?.type === 'NOTIFICATION_CLICKED' && event.data?.notificationId === String(notification.id)) {
        notificationAcknowledgements.acknowledge(notification.id)
        window.focus()
        Promise.resolve(onClick?.()).catch((error) => {
          console.error('处理桌面通知点击失败', error)
        })
      }
    })

    return true
  } catch (error) {
    console.error('展示桌面通知失败', error)
    return false
  }
}
