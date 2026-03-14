import api from './index'

export const getNotifications = (params = {}) => api.get('/notifications/', { params })
export const getUnreadNotificationCount = () => api.get('/notifications/unread-count')
export const markNotificationRead = (notificationId) => api.post(`/notifications/${notificationId}/read`)
export const markAllNotificationsRead = () => api.post('/notifications/read-all')

export const createNotificationSocket = (token) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/api/notifications/ws?token=${encodeURIComponent(token)}`)
}
