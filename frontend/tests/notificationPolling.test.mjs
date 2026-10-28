import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')
const chatNotifications = readFileSync(new URL('../src/composables/useChatNotifications.js', import.meta.url), 'utf8')
const chatNotificationStyles = readFileSync(new URL('../src/components/chat/chatNotifications.css', import.meta.url), 'utf8')

test('通知轮询补偿跨后端 WebSocket 并避免重复提醒', () => {
  assert.match(notificationBell, /NOTIFICATION_POLL_INTERVAL_MS\s*=\s*10 \* 1000/)
  assert.match(notificationBell, /window\.setInterval\(pollNotifications, NOTIFICATION_POLL_INTERVAL_MS\)/)
  assert.match(notificationBell, /notificationPollInFlight/)
  assert.match(notificationBell, /getNotifications\(\{ limit: 10, channel: 'system' \}\)/)
  assert.match(notificationBell, /const seenNotificationIds = new Set\(\)/)
  assert.doesNotMatch(notificationBell, /SEEN_NOTIFICATION_TTL/)
  assert.match(notificationBell, /filter\(\(item\) => rememberNotification\(item\.id\)\)/)
  assert.match(notificationBell, /await loadUnreadCount\(\)[\s\S]*if \(!incomingNotifications\.length\) return/)
  assert.match(notificationBell, /startNotificationPolling\(\)[\s\S]*onBeforeUnmount[\s\S]*stopNotificationPolling\(\)/)
})

test('通知全部已读只处理业务；业务及聊天均不回退网页浮窗', () => {
  assert.match(chatNotifications, /channel: 'chat'/)
  assert.match(chatNotifications, /!isChatMentionNotification\(notification\)/)
  assert.match(chatNotifications, /showDesktopNotification\(notification/)
  assert.match(notificationBell, /markAllNotificationsRead\(\{ channel: 'system' \}\)/)
  assert.doesNotMatch(chatNotifications, /ElNotification|activeMentionNotifications/)
  assert.doesNotMatch(notificationBell, /ElNotification|activeNotificationPopups/)
})
