import { isDesktopAttentionNotification } from './notificationChannels.js'
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
  window.dispatchEvent?.(new Event('desktop-notification-preference-changed'))
  return getDesktopNotificationState()
}

export const disableDesktopNotifications = () => {
  writeBoolean(getStorageKey(PREFERENCE_PREFIX), false)
  window.dispatchEvent?.(new Event('desktop-notification-preference-changed'))
  return getDesktopNotificationState()
}

export const hasSeenDesktopNotificationGuide = () => readBoolean(getStorageKey(GUIDE_PREFIX))

export const markDesktopNotificationGuideSeen = () => {
  writeBoolean(getStorageKey(GUIDE_PREFIX), true)
}

/**
 * 仅展示符合未读数字提醒范围的操作系统通知，不提供网页浮层回退。
 */
// 保持同步返回值约定，手机端的异步结果通过回调反馈。
const showWorkerNotification = (notification, onClick, actor, { onShow, onError }) => {
  if (typeof navigator === 'undefined' || !navigator.serviceWorker?.getRegistration) return false
  const worker = navigator.serviceWorker
  const id = String(notification.id), tag = `xinshi-notification-${id}`
  let unsubscribe = () => {}, registration, disposed = false
  const cleanup = () => { disposed = true; unsubscribe(); worker.removeEventListener('message', onMessage) }
  const close = () => registration?.getNotifications({ tag }).then(items => items.forEach(item => item.close())).catch(() => {})
  const onMessage = event => {
    if (event.data?.notificationId !== id) return
    if (!['NOTIFICATION_CLICKED', 'NOTIFICATION_CLOSED'].includes(event.data.type)) return
    cleanup()
    if (event.data.type !== 'NOTIFICATION_CLICKED' || actor !== getCurrentUserKey()) return
    notificationAcknowledgements.acknowledge(id)
    window.focus()
    Promise.resolve(onClick?.()).catch(error => console.error('处理桌面通知点击失败', error))
  }
  worker.addEventListener('message', onMessage)
  unsubscribe = notificationAcknowledgements.subscribe(value => { if (String(value) === id) { cleanup(); close() } })
  Promise.resolve().then(() => worker.getRegistration('/')).then(async value => {
    registration = value
    if (disposed || actor !== getCurrentUserKey() || notificationAcknowledgements.has(id)) { cleanup(); return }
    if (!registration) throw new Error('浏览器推送尚未就绪')
    await registration.showNotification(notification.title || '新通知', {
      body: notification.content || '', icon: '/favicon.svg', tag,
      data: { notificationId: id, userId: actor, url: '/workbench' },
    })
    if (disposed || actor !== getCurrentUserKey() || notificationAcknowledgements.has(id)) { cleanup(); close(); return }
    onShow?.()
  }).catch(error => { cleanup(); if (actor === getCurrentUserKey() && !notificationAcknowledgements.has(id)) onError?.(error) })
  return true
}

export const showDesktopNotification = (notification, onClick, { onShow, onError } = {}) => {
  if (!isDesktopAttentionNotification(notification) || notificationAcknowledgements.has(notification.id)) return false
  if (!getDesktopNotificationState().enabled) return false
  const actor = getCurrentUserKey()

  try {
    const desktopNotification = new window.Notification(notification.title || '新通知', {
      body: notification.content || '',
      icon: '/favicon.svg',
      tag: notification.id ? `xinshi-notification-${notification.id}` : undefined,
    })
    let failed = false
    const fail = error => {
      if (failed || actor !== getCurrentUserKey() || notificationAcknowledgements.has(notification.id)) return
      failed = true
      unsubscribe()
      desktopNotification.close()
      onError?.(error)
    }
    const unsubscribe = notificationAcknowledgements.subscribe(id => {
      if (id === String(notification.id)) { unsubscribe(); desktopNotification.close() }
    })
    desktopNotification.onclose = unsubscribe
    desktopNotification.onshow = () => { if (!failed && actor === getCurrentUserKey()) onShow?.() }
    desktopNotification.onerror = fail

    desktopNotification.onclick = (event) => {
      event.preventDefault()
      if (actor !== getCurrentUserKey()) { desktopNotification.close(); return }
      notificationAcknowledgements.acknowledge(notification.id)
      window.focus()
      desktopNotification.close()
      Promise.resolve(onClick?.()).catch((error) => {
        console.error('处理桌面通知点击失败', error)
      })
    }
    return true
  } catch (error) {
    if (showWorkerNotification(notification, onClick, actor, { onShow, onError })) return true
    console.error('展示桌面通知失败', error)
    onError?.(error)
    return false
  }
}
