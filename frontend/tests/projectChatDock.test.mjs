import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const dock = readFileSync(new URL('../src/components/chat/ProjectChatDock.vue', import.meta.url), 'utf8')
const dockStore = readFileSync(new URL('../src/composables/useProjectChatDock.js', import.meta.url), 'utf8')
const chatPanel = readFileSync(new URL('../src/components/ProjectChatPanel.vue', import.meta.url), 'utf8')
const annotationPage = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const layout = readFileSync(new URL('../src/layout/index.vue', import.meta.url), 'utf8')
const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')
const realtimeSocket = readFileSync(new URL('../src/utils/realtimeSocket.js', import.meta.url), 'utf8')

test('项目沟通 Dock 全局挂载并支持多窗、最小化和关闭', () => {
  assert.match(layout, /<ProjectChatDock\s*\/>/)
  assert.match(annotationPage, /@click="openProjectChat\(row\)">沟通<\/el-button>/)
  assert.match(annotationPage, /projectType:\s*'annotation'/)
  assert.match(dock, /<Teleport to="body">/)
  assert.match(dock, /v-show="!chatWindow\.minimized"/)
  assert.match(dock, /minimizeChat\(chatWindow\.key\)/)
  assert.match(dock, /restoreChat\(chatWindow\.key\)/)
  assert.match(dock, /closeChat\(chatWindow\.key\)/)
  assert.match(dockStore, /MAX_EXPANDED_WINDOWS\s*=\s*3/)
  assert.match(dockStore, /oldest\.minimized\s*=\s*true/)
  assert.match(dockStore, /const closeAllChats = \(\) =>/)
  assert.match(dock, /onBeforeUnmount\(closeAllChats\)/)
})

test('聊天与通知复用同一个实时连接并保留轮询兜底', () => {
  assert.match(realtimeSocket, /createNotificationSocket/)
  assert.match(realtimeSocket, /window\.setInterval[\s\S]*25000/)
  assert.match(realtimeSocket, /window\.setTimeout[\s\S]*3000/)
  assert.match(notificationBell, /subscribe\('notification', handleSocketNotification\)/)
  assert.match(notificationBell, /subscribe\('snapshot', handleSocketSnapshot\)/)
  assert.doesNotMatch(notificationBell, /const socket = ref/)
  assert.match(chatPanel, /subscribe\('chat_message', handleRealtimeChatMessage\)/)
  assert.match(chatPanel, /subscribe\('connected', handleSocketConnected\)/)
  assert.match(chatPanel, /}, 60000\)/)
  assert.match(chatPanel, /if \(!props\.active \|\| !props\.projectId\) return/)
})

test('实时消息按项目匹配、去重并在非第一页提示用户', () => {
  assert.match(chatPanel, /payload\?\.projectType !== props\.projectType/)
  assert.match(chatPanel, /messages\.value\.some\(item => String\(item\.id\)/)
  assert.match(chatPanel, /pagination\.page > 1/)
  assert.match(chatPanel, /有新消息，返回第一页即可查看/)
  assert.match(chatPanel, /messages\.value = \[payload\.message, \.\.\.messages\.value\]/)
})
