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
      <el-badge :value="badgeTotal" :hidden="badgeTotal === 0" :max="99">
        <el-button class="notification-trigger" circle text aria-label="业务通知" title="业务通知：交接、待处理事项及关键业务动态">
          <el-icon :size="18"><Bell /></el-icon>
        </el-button>
      </el-badge>
    </template>

    <div class="notification-panel">
      <div class="notification-panel__header">
        <span>业务通知</span>
        <el-button
          v-if="unreadCount > 0"
          text
          size="small"
          @click="handleMarkAllRead"
        >
          全部已读
        </el-button>
      </div>

      <p class="notification-panel__hint">交接、待处理事项及关键业务动态；群聊和私聊消息请查看“聊天”。</p>
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
  <ResourceRequestDispatchDialog v-if="dispatchBatchId" :batch-id="dispatchBatchId" @close="dispatchBatchId=''" />
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
const ResourceRequestDispatchDialog=defineAsyncComponent(()=>import('@/views/resource/components/ResourceRequestDispatchDialog.vue'))
const dispatchBatchId=ref('')
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBusinessDateTimeMinute as formatTime } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { isSystemNotification } from '@/utils/notificationChannels'
import { notificationAcknowledgements } from '@/utils/notificationAcknowledgements'
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'
import { closeSocket, ensureConnected, subscribe } from '@/utils/realtimeSocket'
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
const badgeTotal = computed(() => unreadCount.value)
const popoverVisible = ref(false)
const permissionRequesting = ref(false)
const desktopNotificationState = ref(getDesktopNotificationState())
let notificationPollTimer = null
let notificationPollInFlight = false
let unsubscribeNotification = null
let unsubscribeSnapshot = null

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
    const data = await getNotifications({ limit: 10, channel: 'system' })
    notifications.value = Array.isArray(data) ? data.filter(isSystemNotification) : []
    notifications.value.forEach((item) => rememberNotification(item.id))
  } catch (error) {
    console.error('加载通知失败', error)
  }
}

const loadUnreadCount = async () => {
  try {
    const data = await getUnreadNotificationCount({ channel: 'system' })
    unreadCount.value = Number(data?.count || 0)
  } catch (error) {
    console.error('加载未读数失败', error)
  }
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
    window.dispatchEvent(new CustomEvent('business-notifications-changed'))
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
  if(item.notification_type==='resource_request_dispatch' && item.related_entity_id){popoverVisible.value=false;dispatchBatchId.value=String(item.related_entity_id);return}
  if(item.notification_type==='chat_summary'&&item.related_entity_id){useProjectChatDock().openFullscreen();await nextTick();window.dispatchEvent(new CustomEvent('chat-open-summary',{detail:{issueId:item.related_entity_id}}));return}
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
      await router.push({ name: routeName, query })
      return
    }
  }
  if (item.related_project_id) {
    const targetTab = 'overview'
    await router.push({ path: '/translation', query: { projectId: item.related_project_id, tab: targetTab } })
    return
  }
  popoverVisible.value = true
}

const activateNotification = async (item, showError = false) => {
  notificationAcknowledgements.acknowledge(item.id)
  window.focus()
  await markItemRead(item, showError)
  try {
    popoverVisible.value = false
    await navigateToNotification(item)
  } catch (error) {
    console.error('跳转通知目标失败', error)
    popoverVisible.value = true
    if (showError) ElMessage.error('无法打开通知目标，已为你打开通知列表')
  }
}

const displayIncomingNotification = (notification) => {
  if (!isSystemNotification(notification) || notification.is_read || notificationAcknowledgements.has(notification.id)) return
  showDesktopNotification(notification, () => activateNotification(notification))
}

// WebSocket 连接只在当前后端进程内生效。轮询用于补偿局域网与云端后端之间的通知同步。
const pollNotifications = async () => {
  if (notificationPollInFlight || !localStorage.getItem('token')) return

  notificationPollInFlight = true
  try {
    const data = await getNotifications({ limit: 10, channel: 'system' })
    const latestNotifications = Array.isArray(data) ? data.filter(isSystemNotification) : []
    const incomingNotifications = latestNotifications.filter((item) => rememberNotification(item.id))

    notifications.value = latestNotifications
    await loadUnreadCount()
    if (!incomingNotifications.length) return
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

// 旧快照的 business 数量含会话业务通知，不能用于系统铃铛。
const handleSocketSnapshot = () => { loadUnreadCount() }

const handleSocketNotification = (payload) => {
  const notification = payload?.notification
  if (!notification || !isSystemNotification(notification) || !rememberNotification(notification.id)) return
  upsertNotification(notification)
  unreadCount.value += notification.is_read ? 0 : 1
  if (notification.notification_type === 'workflow_handover_pending') {
    window.dispatchEvent(new CustomEvent('workflow-handover-pending'))
  }
  if (notification.notification_type === 'project_manager_handover_pending') {
    window.dispatchEvent(new CustomEvent('project-manager-handover-pending'))
  }
  displayIncomingNotification(notification)
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
    await markAllNotificationsRead({ channel: 'system' })
    for (const id of notifications.value.map(item => item.id)) notificationAcknowledgements.acknowledge(id)
    notifications.value = notifications.value.map((item) => ({ ...item, is_read: true }))
    unreadCount.value = 0
    window.dispatchEvent(new CustomEvent('business-notifications-changed'))
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '批量已读失败'))
  }
}

onMounted(() => {
  syncDesktopNotificationState()
  loadNotifications()
  loadUnreadCount()
  unsubscribeSnapshot = subscribe('snapshot', handleSocketSnapshot)
  unsubscribeNotification = subscribe('notification', handleSocketNotification)
  ensureConnected()
  startNotificationPolling()
  window.addEventListener('business-notifications-changed', handlePopoverShow)
  window.addEventListener('focus', syncDesktopNotificationState)
})

onBeforeUnmount(() => {
  window.removeEventListener('business-notifications-changed', handlePopoverShow)
  unsubscribeSnapshot?.()
  unsubscribeNotification?.()
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

</style>

<style scoped>.notification-panel__hint{margin:0;color:var(--el-text-color-secondary);font-size:12px;line-height:1.6}</style>
<style>.notification-popover{z-index:100001!important;max-width:calc(100vw - 32px)}</style>
