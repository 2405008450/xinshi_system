import { onMounted, onBeforeUnmount } from 'vue'
import api from '@/api/index'
import { chatClientType } from '@/utils/chatDevice'
import { subscribe } from '@/utils/realtimeSocket'
import { newChatRequestId } from '@/utils/chatTopics'

export function useDesktopHeartbeat() {
  const clientId = newChatRequestId()
  let sequence = 0, timer, lastSent = 0, inFlight = false, disposed = false, paused = false
  let controller, actor = '', cleanups = []
  async function heartbeat(force = false) {
    if (disposed || paused || chatClientType(navigator) !== 'desktop') return
    const token = localStorage.getItem('token'), userId = localStorage.getItem('user_id')
    if (!token || !userId || inFlight || !force && Date.now() - lastSent < 20000) return
    inFlight = true; actor = userId
    const current = new AbortController(); controller = current
    lastSent = Date.now()
    try {
      await api.post('/chat/presence/heartbeat', { client_id: clientId, sequence: ++sequence, active: true },
        { signal: current.signal, headers: { 'X-Client-Type': 'desktop' }, timeout: 10000 })
    } catch { lastSent = 0 } // 短暂断网后允许立即恢复上报。
    finally { inFlight = false }
  }
  const refresh = () => { paused = false; void heartbeat(true) }
  function release() {
    if (paused) return
    paused = true; controller?.abort()
    const token = localStorage.getItem('token')
    if (!actor || actor !== localStorage.getItem('user_id') || !token) return
    // 关闭页面也能送达；高序号防止已取消的旧心跳随后把状态恢复为在线。
    void fetch('/api/chat/presence/heartbeat', { method: 'POST', keepalive: true,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', 'X-Client-Type': 'desktop' },
      body: JSON.stringify({ client_id: clientId, sequence: ++sequence, active: false }),
    }).catch(() => {})
  }
  onMounted(() => {
    void heartbeat(true)
    timer = window.setInterval(() => void heartbeat(), 25000)
    cleanups = [subscribe('connected', refresh), subscribe('foreground', refresh),
      subscribe('presence-heartbeat', () => void heartbeat())]
    window.addEventListener('online', refresh)
    window.addEventListener('pageshow', refresh)
    window.addEventListener('pagehide', release)
    window.addEventListener('auth-session-clearing', release)
  })
  onBeforeUnmount(() => {
    disposed = true; window.clearInterval(timer); release(); controller?.abort()
    cleanups.forEach(cleanup => cleanup()); window.removeEventListener('online', refresh)
    window.removeEventListener('pageshow', refresh)
    window.removeEventListener('pagehide', release)
    window.removeEventListener('auth-session-clearing', release)
  })
}
