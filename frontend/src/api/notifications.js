import api from './index'
import { chatClientType } from '@/utils/chatDevice'
import { notificationAcknowledgements } from '@/utils/notificationAcknowledgements'

export const getNotifications = async (params = {}, config = {}) => {
  const actor = notificationAcknowledgements.actor()
  const result = await api.get('/notifications/', { ...config, params,paramsSerializer:{indexes:null} })
  notificationAcknowledgements.rememberRead(Array.isArray(result) ? result : [], actor)
  return result
}
export const getNotificationPage = async (params = {}, config = {}) => {
  const actor = notificationAcknowledgements.actor()
  const result = await api.get('/notifications/page', { ...config, params,paramsSerializer:{indexes:null} })
  notificationAcknowledgements.rememberRead(result?.items || [], actor)
  return result
}
export const getUnreadNotificationCount = (params = {}, config = {}) => api.get('/notifications/unread-count', { ...config,params,paramsSerializer:{indexes:null} })
export const markNotificationRead = async (notificationId) => {
  const actor = notificationAcknowledgements.actor()
  const result = await api.post(`/notifications/${notificationId}/read`)
  notificationAcknowledgements.rememberRead([{ id: notificationId, is_read: true }], actor)
  return result
}
export const markAllNotificationsRead = (params = {}) => api.post('/notifications/read-all', null, { params })

export const createNotificationSocket = (token) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/api/notifications/ws?token=${encodeURIComponent(token)}&client_type=${chatClientType(navigator)}`)
}
