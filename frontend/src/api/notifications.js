import api from './index'

export const getNotifications = (params = {}, config = {}) => api.get('/notifications/', { ...config, params })
export const getUnreadNotificationCount = (params = {}) => api.get('/notifications/unread-count', { params })
export const markNotificationRead = (notificationId) => api.post(`/notifications/${notificationId}/read`)
export const markAllNotificationsRead = (params = {}) => api.post('/notifications/read-all', null, { params })

export const createNotificationSocket = (token) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/api/notifications/ws?token=${encodeURIComponent(token)}`)
}
