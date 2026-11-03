import api from '@/api'
import { getDesktopNotificationState } from './desktopNotifications.js'

let generation = 0
export async function syncWebPushSubscription() {
  const version = ++generation, actor = localStorage.getItem('user_id')
  if (!window.isSecureContext || !navigator.serviceWorker || !window.PushManager || !actor) return
  const current = () => version === generation && actor === localStorage.getItem('user_id')
  const registration = await navigator.serviceWorker.register('/sw.js')
  if (!current()) return
  if (!getDesktopNotificationState().enabled) return stopWebPushSubscription()
  const { publicKey } = await api.get('/push/public_key')
  if (!current() || !publicKey) return
  await navigator.serviceWorker.ready
  if (!current()) return
  const padding = '='.repeat((4 - publicKey.length % 4) % 4)
  const decoded = window.atob((publicKey + padding).replace(/-/g, '+').replace(/_/g, '/'))
  const key = Uint8Array.from(decoded, value => value.charCodeAt(0))
  const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })
  if (!current()) { await subscription.unsubscribe(); return }
  const data = subscription.toJSON()
  await api.post('/push/subscribe', { endpoint: data.endpoint, p256dh: data.keys.p256dh, auth: data.keys.auth })
}

export async function stopWebPushSubscription() {
  const version = ++generation
  if (!navigator.serviceWorker?.getRegistration) return
  const registration = await navigator.serviceWorker.getRegistration('/')
  if (version !== generation) return
  const subscription = await registration?.pushManager.getSubscription()
  if (version === generation && subscription) await subscription.unsubscribe()
}
