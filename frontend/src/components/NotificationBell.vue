<template>
  <el-popover
    v-model:visible="popoverVisible"
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
        <span>通知</span>
        <el-button
          v-if="unreadCount > 0"
          text
          size="small"
          @click="handleMarkAllRead"
        >
          全部已读
        </el-button>
      </div>

      <div class="desktop-notification-card" :class="`desktop-notification-card--${desktopStatus.type}`">
        <div class="desktop-notification-card__content">
          <div class="desktop-notification-card__title">
            <span class="desktop-notification-card__dot" />
            {{ desktopStatus.title }}
          </div>
          <div class="desktop-notification-card__description">{{ desktopStatus.description }}</div>
        </div>
        <el-button
          v-if="desktopStatus.action === 'enable'"
          size="small"
          type="primary"
          :loading="permissionRequesting"
          @click="handleEnableDesktopNotifications"
        >
          启用
        </el-button>
        <el-button
          v-else-if="desktopStatus.action === 'disable'"
          size="small"
          text
          @click="handleDisableDesktopNotifications"
        >
          关闭
        </el-button>
        <el-button
          v-else-if="desktopStatus.action === 'help'"
          size="small"
          text
          @click="showPermissionHelp"
        >
          查看方法
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
              <span v-if="!item.is_read">未读</span>
            </div>
          </button>
        </div>
        <el-empty v-else description="暂无通知" :image-size="72" />
      </el-scrollbar>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { formatDateTimeMinute as formatTime } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import {
  createNotificationSocket,
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'
import {
  disableDesktopNotifications,
  enableDesktopNotifications,
  getDesktopNotificationState,
  hasSeenDesktopNotificationGuide,
  markDesktopNotificationGuideSeen,
  showDesktopNotification,
} from '../utils/desktopNotifications'

const router = useRouter()
const notifications = ref([])
const unreadCount = ref(0)
const popoverVisible = ref(false)
const permissionRequesting = ref(false)
const desktopNotificationState = ref(getDesktopNotificationState())
const socket = ref(null)
let reconnectTimer = null
let heartbeatTimer = null
let notificationPollTimer = null
let notificationPollInFlight = false
let allowReconnect = true

const seenNotificationIds = new Set()
const readingNotificationIds = new Set()
const MAX_SEEN_NOTIFICATIONS = 200
const NOTIFICATION_POLL_INTERVAL_MS = 10 * 1000

const desktopStatus = computed(() => {
  const state = desktopNotificationState.value
  if (!state.supported) {
    return { type: 'unavailable', title: '桌面通知不可用', description: '当前浏览器不支持系统通知。', action: null }
  }
  if (!state.secure) {
    return { type: 'unavailable', title: '桌面通知需要 HTTPS', description: '请通过公司提供的 HTTPS 域名访问系统。', action: null }
  }
  if (state.permission === 'denied') {
    return { type: 'denied', title: '桌面通知已被拒绝', description: '请在浏览器的网站权限中改为允许。', action: 'help' }
  }
  if (state.enabled) {
    return { type: 'enabled', title: '桌面通知已启用', description: '新通知将显示在 Windows 通知中心。', action: 'disable' }
  }
  return {
    type: 'disabled',
    title: '桌面通知未启用',
    description: state.permission === 'granted' ? '浏览器已授权，可随时重新启用。' : '启用后，网页最小化时也能及时看到提醒。',
    action: 'enable',
  }
})

const syncDesktopNotificationState = () => {
  desktopNotificationState.value = getDesktopNotificationState()
}

const rememberNotification = (notificationId) => {
  if (!notificationId) return true
  const id = String(notificationId)
  if (seenNotificationIds.has(id)) return false
  seenNotificationIds.add(id)
  while (seenNotificationIds.size > MAX_SEEN_NOTIFICATIONS) {
    seenNotificationIds.delete(seenNotificationIds.values().next().value)
  }
  return true
}

const loadNotifications = async () => {
  try {
    const data = await getNotifications({ limit: 10 })
    notifications.value = Array.isArray(data) ? data : []
    notifications.value.forEach((item) => rememberNotification(item.id))
  } catch (error) {
    console.error('加载通知失败', error)
  }
}

const loadUnreadCount = async () => {
  try {
    const data = await getUnreadNotificationCount()
    unreadCount.value = Number(data?.count || 0)
  } catch (error) {
    console.error('加载未读数失败', error)
  }
}

const closeSocket = (preserveReconnect = false) => {
  if (!preserveReconnect) allowReconnect = false
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

const markItemRead = async (item, showError = false) => {
  if (!item?.id || item.is_read) return true
  const id = String(item.id)
  if (readingNotificationIds.has(id)) return false
  readingNotificationIds.add(id)
  try {
    await markNotificationRead(item.id)
    item.is_read = true
    const listItem = notifications.value.find((candidate) => String(candidate.id) === id)
    if (listItem) listItem.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    return true
  } catch (error) {
    console.error('标记通知已读失败', error)
    if (showError) ElMessage.error(getLocalizedErrorMessage(error, '更新通知失败'))
    return false
  } finally {
    readingNotificationIds.delete(id)
  }
}

const navigateToNotification = async (item) => {
  if (['workflow_handover_pending', 'project_manager_handover_pending'].includes(item.notification_type)) {
    await router.push('/workbench')
    return
  }
  if (item.related_project_type && item.related_entity_id) {
    const routeName = {
      translation: 'TranslationProjectDetails',
      interpretation: 'InterpretationProjectDetails',
      annotation: 'AnnotationProjectDetails',
      recruitment: 'RecruitmentProjectDetails',
    }[item.related_project_type]
    if (routeName) {
      const query = { projectId: item.related_entity_id }
      if (String(item.notification_type || '').includes('project_chat')) query.tab = 'chat'
      await router.push({ name: routeName, query })
      return
    }
  }
  if (item.related_project_id) {
    const targetTab = String(item.notification_type || '').startsWith('project_chat') ? 'chat' : 'overview'
    await router.push({ path: '/translation', query: { projectId: item.related_project_id, tab: targetTab } })
    return
  }
  popoverVisible.value = true
}

const activateNotification = async (item, showError = false) => {
  window.focus()
  await markItemRead(item, showError)
  try {
    await navigateToNotification(item)
  } catch (error) {
    console.error('跳转通知目标失败', error)
    popoverVisible.value = true
    if (showError) ElMessage.error('无法打开通知目标，已为你打开通知列表')
  }
}

const displayIncomingNotification = (notification) => {
  const displayed = showDesktopNotification(notification, () => activateNotification(notification))
  const isMention = String(notification.notification_type || '').endsWith('_mention')

  if (isMention) {
    ElNotification({
      title: '有人在项目沟通中 @了你',
      message: notification.content,
      type: 'warning',
      position: 'top-right',
      duration: 12000,
      showClose: true,
      customClass: 'mention-notification',
      onClick: () => activateNotification(notification, true),
    })
    return
  }

  if (displayed) return
  ElNotification({
    title: notification.title,
    message: notification.content,
    position: 'top-right',
    duration: 4000,
  })
}

// WebSocket 连接只在当前后端进程内生效。轮询用于补偿局域网与云端后端之间的通知同步。
const pollNotifications = async () => {
  if (notificationPollInFlight || !localStorage.getItem('token')) return

  notificationPollInFlight = true
  try {
    const data = await getNotifications({ limit: 10 })
    const latestNotifications = Array.isArray(data) ? data : []
    const incomingNotifications = latestNotifications.filter((item) => rememberNotification(item.id))

    notifications.value = latestNotifications
    if (!incomingNotifications.length) return

    await loadUnreadCount()
    // 接口按时间倒序返回；按正序弹出，避免多条提醒遮挡时顺序颠倒。
    incomingNotifications.slice().reverse().forEach(displayIncomingNotification)
  } catch (error) {
    console.error('轮询通知失败', error)
  } finally {
    notificationPollInFlight = false
  }
}

const startNotificationPolling = () => {
  if (notificationPollTimer) window.clearInterval(notificationPollTimer)
  notificationPollTimer = window.setInterval(pollNotifications, NOTIFICATION_POLL_INTERVAL_MS)
}

const stopNotificationPolling = () => {
  if (!notificationPollTimer) return
  window.clearInterval(notificationPollTimer)
  notificationPollTimer = null
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
      if (payload?.type === 'pong') return
      if (payload?.type === 'notification' && payload.notification) {
        if (!rememberNotification(payload.notification.id)) return
        upsertNotification(payload.notification)
        unreadCount.value += payload.notification.is_read ? 0 : 1
        if (payload.notification.notification_type === 'workflow_handover_pending') {
          window.dispatchEvent(new CustomEvent('workflow-handover-pending'))
        }
        if (payload.notification.notification_type === 'project_manager_handover_pending') {
          window.dispatchEvent(new CustomEvent('project-manager-handover-pending'))
        }
        displayIncomingNotification(payload.notification)
      }
    } catch (error) {
      console.error('解析通知消息失败', error)
    }
  }

  ws.onopen = () => {
    if (heartbeatTimer) window.clearInterval(heartbeatTimer)
    heartbeatTimer = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
  }

  ws.onclose = () => {
    if (heartbeatTimer) {
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (allowReconnect && localStorage.getItem('token')) scheduleReconnect()
  }

  ws.onerror = () => ws.close()
}

const handlePopoverShow = () => {
  syncDesktopNotificationState()
  loadNotifications()
  loadUnreadCount()
}

const handleNotificationClick = (item) => activateNotification(item, true)

const showPermissionHelp = () => ElMessageBox.alert(
  '点击地址栏左侧的网站信息图标，将“通知”改为“允许”，然后刷新页面。还需确认 Windows“设置 → 系统 → 通知”中已开启 Edge 或 Chrome 通知。',
  '开启桌面通知',
  { confirmButtonText: '知道了' }
)

const handleEnableDesktopNotifications = async () => {
  permissionRequesting.value = true
  try {
    desktopNotificationState.value = await enableDesktopNotifications()
    if (desktopNotificationState.value.enabled) {
      ElMessage.success('桌面通知已启用')
      if (!hasSeenDesktopNotificationGuide()) {
        markDesktopNotificationGuideSeen()
        await ElMessageBox.alert(
          '桌面通知已经启用。请确保 Windows“设置 → 系统 → 通知”中也已开启 Edge 或 Chrome 通知。',
          '桌面通知使用提示',
          { confirmButtonText: '知道了' }
        )
      }
    } else if (desktopNotificationState.value.permission === 'denied') {
      await showPermissionHelp()
    }
  } catch (error) {
    console.error('申请桌面通知权限失败', error)
    ElMessage.error('无法启用桌面通知，请检查浏览器设置')
  } finally {
    permissionRequesting.value = false
  }
}

const handleDisableDesktopNotifications = () => {
  desktopNotificationState.value = disableDesktopNotifications()
  ElMessage.success('已关闭本系统的桌面通知')
}

const handleMarkAllRead = async () => {
  try {
    await markAllNotificationsRead()
    notifications.value = notifications.value.map((item) => ({ ...item, is_read: true }))
    unreadCount.value = 0
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '批量已读失败'))
  }
}

onMounted(() => {
  syncDesktopNotificationState()
  loadNotifications()
  loadUnreadCount()
  connectSocket()
  startNotificationPolling()
  window.addEventListener('focus', syncDesktopNotificationState)
})

onBeforeUnmount(() => {
  closeSocket()
  stopNotificationPolling()
  window.removeEventListener('focus', syncDesktopNotificationState)
})

</script>

<style scoped>
.notification-trigger {
  color: var(--color-text-secondary);
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

.desktop-notification-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-page-bg);
}

.desktop-notification-card__content {
  flex: 1;
  min-width: 0;
}

.desktop-notification-card__title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.desktop-notification-card__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
}

.desktop-notification-card--enabled .desktop-notification-card__dot {
  background: #22c55e;
}

.desktop-notification-card--denied .desktop-notification-card__dot,
.desktop-notification-card--unavailable .desktop-notification-card__dot {
  background: #f59e0b;
}

.desktop-notification-card__description {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--color-text-muted);
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notification-item {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.notification-item:hover {
  border-color: #cbd5e1;
  background: var(--color-page-bg);
}

.notification-item--unread {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.notification-item__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.notification-item__content {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.notification-item__meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--color-text-muted);
}

:global(.el-notification.mention-notification) {
  width: min(420px, calc(100vw - 32px));
  border: 2px solid var(--el-color-warning);
  background: var(--el-color-warning-light-9);
  box-shadow: 0 16px 36px rgb(15 23 42 / 24%);
  cursor: pointer;
}

:global(.mention-notification .el-notification__title) {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
}

:global(.mention-notification .el-notification__content) {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
</style>
