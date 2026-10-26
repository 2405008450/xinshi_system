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
let lastActivityAt = 0
let lastResumeAt = 0
let lifecycleBound = false
let wasHidden = false

// 手机页面可能冻结后保留 OPEN 状态；恢复时不能只看 readyState。
const resumeConnection = event => {
  if (document.visibilityState === 'hidden') { wasHidden = true; return }
  if (!allowReconnect || !localStorage.getItem('token')) return
  const now = Date.now()
  const reconnect = wasHidden || event.type === 'online' || event.type === 'resume' || !!event.persisted
  wasHidden = false
  if (!reconnect && lastResumeAt && now - lastResumeAt < 750) return
  lastResumeAt = now
  const stale = socket && now - lastActivityAt > (socket.readyState === WebSocket.CONNECTING ? 15000 : 45000)
  ensureConnected({ force: !!stale || reconnect })
  emit('foreground', { type: 'foreground' })
}

const bindLifecycle = () => {
  if (lifecycleBound) return
  lifecycleBound = true
  wasHidden = document.visibilityState === 'hidden'
  document.addEventListener('visibilitychange', resumeConnection)
  document.addEventListener('resume', resumeConnection)
  for (const event of ['pageshow', 'online', 'focus']) window.addEventListener(event, resumeConnection)
}

const unbindLifecycle = () => {
  if (!lifecycleBound) return
  lifecycleBound = false
  document.removeEventListener('visibilitychange', resumeConnection)
  document.removeEventListener('resume', resumeConnection)
  for (const event of ['pageshow', 'online', 'focus']) window.removeEventListener(event, resumeConnection)
}

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

export const ensureConnected = ({ force = false } = {}) => {
  const token = localStorage.getItem('token') || ''
  if (!token) {
    closeSocket()
    return null
  }
  if (
    !force && socketToken === token
    && socket
    && [WebSocket.CONNECTING, WebSocket.OPEN].includes(socket.readyState)
  ) {
    return socket
  }

  allowReconnect = true
  bindLifecycle()
  clearReconnectTimer()
  clearHeartbeatTimer()
  const previous = socket
  socket = null
  if (previous) previous.close()

  const currentSocket = createNotificationSocket(token)
  socket = currentSocket
  socketToken = token
  lastActivityAt = Date.now()

  currentSocket.onmessage = (event) => {
    if (socket !== currentSocket) return
    lastActivityAt = Date.now()
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
    lastActivityAt = Date.now()
    clearHeartbeatTimer()
    annotationWatches.forEach((_, id) => sendAnnotationWatch(id, true))
    heartbeatTimer = window.setInterval(() => {
      if (socket !== currentSocket) return
      if (Date.now() - lastActivityAt > 75000) { ensureConnected({ force: true }); return }
      if (currentSocket.readyState === WebSocket.OPEN) {
        try { currentSocket.send('ping') } catch { currentSocket.close() }
      }
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
  unbindLifecycle()
  lastResumeAt = 0
  wasHidden = false
  const currentSocket = socket
  socket = null
  socketToken = ''
  if (currentSocket) currentSocket.close()
}
