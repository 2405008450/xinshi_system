self.addEventListener('install', event => event.waitUntil(self.skipWaiting()))
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()))

const localUrl = value => {
  const url = new URL(value || '/workbench', self.location.origin)
  return url.origin === self.location.origin ? url.href : self.location.origin + '/workbench'
}
self.addEventListener('push', event => {
  let data = {}
  try { data = event.data?.json() || {} } catch { data = { body: '你有一条未读消息' } }
  event.waitUntil(self.registration.showNotification(data.title || '新消息通知', {
    body: data.body || '你有一条未读消息', icon: '/favicon.svg',
    data: { url: localUrl(data.url), userId: data.userId },
  }))
})
self.addEventListener('notificationclick', event => {
  event.notification.close()
  const data = event.notification.data || {}
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async windows => {
    const client = windows.find(item => new URL(item.url).origin === self.location.origin)
    if (client) {
      if (data.notificationId) client.postMessage({ type: 'NOTIFICATION_CLICKED', notificationId: String(data.notificationId), userId: data.userId })
      else await client.navigate(localUrl(data.url))
      return client.focus()
    }
    return self.clients.openWindow(localUrl(data.url))
  }))
})
self.addEventListener('notificationclose', event => {
  const data = event.notification.data || {}
  if (data.notificationId) event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windows => {
    windows.forEach(client => client.postMessage({ type: 'NOTIFICATION_CLOSED', notificationId: String(data.notificationId) }))
  }))
})
