import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')

test('通知轮询补偿跨后端 WebSocket 并避免重复提醒', () => {
  assert.match(notificationBell, /NOTIFICATION_POLL_INTERVAL_MS\s*=\s*10 \* 1000/)
  assert.match(notificationBell, /window\.setInterval\(pollNotifications, NOTIFICATION_POLL_INTERVAL_MS\)/)
  assert.match(notificationBell, /notificationPollInFlight/)
  assert.match(notificationBell, /getNotifications\(\{ limit: 10 \}\)/)
  assert.match(notificationBell, /const seenNotificationIds = new Set\(\)/)
  assert.doesNotMatch(notificationBell, /SEEN_NOTIFICATION_TTL/)
  assert.match(notificationBell, /filter\(\(item\) => rememberNotification\(item\.id\)\)/)
  assert.match(notificationBell, /if \(!incomingNotifications\.length\) return[\s\S]*await loadUnreadCount\(\)/)
  assert.match(notificationBell, /startNotificationPolling\(\)[\s\S]*onBeforeUnmount[\s\S]*stopNotificationPolling\(\)/)
})

test('@ 通知在网页右上角使用醒目且可点击的长时提醒', () => {
  assert.match(notificationBell, /endsWith\('_mention'\)/)
  assert.match(notificationBell, /title: '有人在项目沟通中 @了你'/)
  assert.match(notificationBell, /position: 'top-right'/)
  assert.match(notificationBell, /duration: 12000/)
  assert.match(notificationBell, /customClass: 'mention-notification'/)
  assert.match(notificationBell, /onClick: \(\) => activateNotification\(notification, true\)/)
  assert.match(notificationBell, /\.el-notification\.mention-notification/)
})
