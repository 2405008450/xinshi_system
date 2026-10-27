import api from './index'
import { chatClientType } from '@/utils/chatDevice'

export const getNotifications = (params = {}, config = {}) => api.get('/notifications/', { ...config, params,paramsSerializer:{indexes:null} })
export const getNotificationPage = (params = {}, config = {}) => api.get('/notifications/page', { ...config, params,paramsSerializer:{indexes:null} })
export const getUnreadNotificationCount = (params = {}, config = {}) => api.get('/notifications/unread-count', { ...config,params,paramsSerializer:{indexes:null} })
export const markNotificationRead = (notificationId) => api.post(`/notifications/${notificationId}/read`)
export const markAllNotificationsRead = (params = {}) => api.post('/notifications/read-all', null, { params })

export const createNotificationSocket = (token) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/api/notifications/ws?token=${encodeURIComponent(token)}&client_type=${chatClientType(navigator)}`)
}
