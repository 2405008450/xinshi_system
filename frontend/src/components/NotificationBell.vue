<template>
  <el-popover
    placement="bottom-end"
    :width="360"
    trigger="click"
    popper-class="notification-popover"
    @show="handlePopoverShow"
  >
    <template #reference>
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-button class="notification-trigger" circle text>
          <el-icon :size="18"><Bell /></el-icon>
        </el-button>
      </el-badge>
    </template>

    <div class="notification-panel">
      <div class="notification-panel__header">
        <span>Notifications</span>
        <el-button
          v-if="unreadCount > 0"
          text
          size="small"
          @click="handleMarkAllRead"
        >
          Mark all read
        </el-button>
      </div>
      <el-scrollbar max-height="360px">
        <div v-if="notifications.length" class="notification-list">
          <button
            v-for="item in notifications"
            :key="item.id"
            class="notification-item"
            :class="{ 'notification-item--unread': !item.is_read }"
            @click="handleNotificationClick(item)"
          >
            <div class="notification-item__title">{{ item.title }}</div>
            <div class="notification-item__content">{{ item.content }}</div>
            <div class="notification-item__meta">
              <span>{{ formatTime(item.created_at) }}</span>
              <span v-if="!item.is_read">Unread</span>
            </div>
          </button>
        </div>
        <el-empty v-else description="No notifications" :image-size="72" />
      </el-scrollbar>
    </div>
  </el-popover>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { ElMessage, ElNotification } from 'element-plus'
import {
  createNotificationSocket,
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'

const router = useRouter()
const notifications = ref([])
const unreadCount = ref(0)
const socket = ref(null)
let reconnectTimer = null
let heartbeatTimer = null
let allowReconnect = true

const loadNotifications = async () => {
  try {
    const data = await getNotifications({ limit: 10 })
    notifications.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('Failed to load notifications', error)
  }
}

const loadUnreadCount = async () => {
  try {
    const data = await getUnreadNotificationCount()
    unreadCount.value = Number(data?.count || 0)
  } catch (error) {
    console.error('Failed to load unread count', error)
  }
}

const closeSocket = (preserveReconnect = false) => {
  if (!preserveReconnect) {
    allowReconnect = false
  }
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
  if (socket.value) {
    socket.value.close()
    socket.value = null
  }
}

const scheduleReconnect = () => {
  if (reconnectTimer) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connectSocket()
  }, 3000)
}

const upsertNotification = (notification) => {
  const current = notifications.value.filter((item) => item.id !== notification.id)
  notifications.value = [notification, ...current].slice(0, 10)
}

const connectSocket = () => {
  const token = localStorage.getItem('token')
  if (!token) return

  allowReconnect = true
  closeSocket(true)
  const ws = createNotificationSocket(token)
  socket.value = ws

  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      if (payload?.type === 'snapshot') {
        unreadCount.value = Number(payload.unread_count || 0)
        return
      }
      if (payload?.type === 'pong') {
        return
      }
      if (payload?.type === 'notification' && payload.notification) {
        upsertNotification(payload.notification)
        unreadCount.value += payload.notification.is_read ? 0 : 1
        ElNotification({
          title: payload.notification.title,
          message: payload.notification.content,
          duration: 4000,
        })
      }
    } catch (error) {
      console.error('Failed to parse notification payload', error)
    }
  }

  ws.onopen = () => {
    if (heartbeatTimer) {
      window.clearInterval(heartbeatTimer)
    }
    heartbeatTimer = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 25000)
  }

  ws.onclose = () => {
    if (heartbeatTimer) {
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (allowReconnect && localStorage.getItem('token')) {
      scheduleReconnect()
    }
  }

  ws.onerror = () => {
    ws.close()
  }
}

const handlePopoverShow = () => {
  loadNotifications()
  loadUnreadCount()
}

const handleNotificationClick = async (item) => {
  try {
    if (!item.is_read) {
      await markNotificationRead(item.id)
      item.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
    if (item.related_project_id) {
      router.push({ path: '/translation', query: { projectId: item.related_project_id } })
    }
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || 'Failed to update notification')
  }
}

const handleMarkAllRead = async () => {
  try {
    await markAllNotificationsRead()
    notifications.value = notifications.value.map((item) => ({ ...item, is_read: true }))
    unreadCount.value = 0
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || 'Failed to mark notifications read')
  }
}

onMounted(() => {
  loadNotifications()
  loadUnreadCount()
  connectSocket()
})

onBeforeUnmount(() => {
  closeSocket()
})

const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString()
}
</script>

<style scoped>
.notification-trigger {
  color: #4a5568;
}

.notification-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.notification-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notification-item {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.notification-item:hover {
  border-color: #93c5fd;
  background: #f8fbff;
}

.notification-item--unread {
  border-color: #60a5fa;
  background: #eff6ff;
}

.notification-item__title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

.notification-item__content {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #4b5563;
}

.notification-item__meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #6b7280;
}
</style>
