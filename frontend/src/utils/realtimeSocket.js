import { createNotificationSocket } from '@/api/notifications'

const subscribers = new Map()
const annotationWatches = new Map()
const sendAnnotationWatch = (projectId, active) => {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'annotation_chat_watch', projectId, active }))
}
export const watchAnnotationChat = projectId => {
  const id = String(projectId)
  annotationWatches.set(id, (annotationWatches.get(id) || 0) + 1)
  ensureConnected()
  sendAnnotationWatch(id, true)
  return () => {
    const count = (annotationWatches.get(id) || 1) - 1
    if (count) annotationWatches.set(id, count)
    else { annotationWatches.delete(id); sendAnnotationWatch(id, false) }
  }
}

let socket = null
let socketToken = ''
let reconnectTimer = null
let heartbeatTimer = null
let allowReconnect = true

const emit = (type, payload) => {
  const handlers = subscribers.get(type)
  if (!handlers) return
  handlers.forEach((handler) => {
    try {
      handler(payload)
    } catch (error) {
      console.error(`处理实时消息失败：${type}`, error)
    }
  })
}

const clearReconnectTimer = () => {
  if (!reconnectTimer) return
  window.clearTimeout(reconnectTimer)
  reconnectTimer = null
}

const clearHeartbeatTimer = () => {
  if (!heartbeatTimer) return
  window.clearInterval(heartbeatTimer)
  heartbeatTimer = null
}

const scheduleReconnect = () => {
  if (reconnectTimer || !allowReconnect || !localStorage.getItem('token')) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    ensureConnected()
  }, 3000)
}

export const ensureConnected = () => {
  const token = localStorage.getItem('token') || ''
  if (!token) {
    closeSocket()
    return null
  }
  if (
    socketToken === token
    && socket
    && [WebSocket.CONNECTING, WebSocket.OPEN].includes(socket.readyState)
  ) {
    return socket
  }

  allowReconnect = true
  clearReconnectTimer()
  clearHeartbeatTimer()
  if (socket) socket.close()

  const currentSocket = createNotificationSocket(token)
  socket = currentSocket
  socketToken = token

  currentSocket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      if (!payload?.type || payload.type === 'pong') return
      emit(payload.type, payload)
    } catch (error) {
      console.error('解析实时消息失败', error)
    }
  }

  currentSocket.onopen = () => {
    if (socket !== currentSocket) return
    clearHeartbeatTimer()
    annotationWatches.forEach((_, id) => sendAnnotationWatch(id, true))
    heartbeatTimer = window.setInterval(() => {
      if (currentSocket.readyState === WebSocket.OPEN) currentSocket.send('ping')
    }, 25000)
    emit('connected', { type: 'connected' })
  }

  currentSocket.onclose = () => {
    if (socket !== currentSocket) return
    socket = null
    clearHeartbeatTimer()
    scheduleReconnect()
  }

  currentSocket.onerror = () => currentSocket.close()
  return currentSocket
}

export const subscribe = (type, handler) => {
  if (!subscribers.has(type)) subscribers.set(type, new Set())
  subscribers.get(type).add(handler)
  return () => {
    const handlers = subscribers.get(type)
    if (!handlers) return
    handlers.delete(handler)
    if (!handlers.size) subscribers.delete(type)
  }
}

export const closeSocket = () => {
  allowReconnect = false
  clearReconnectTimer()
  clearHeartbeatTimer()
  const currentSocket = socket
  socket = null
  socketToken = ''
  if (currentSocket) currentSocket.close()
}
