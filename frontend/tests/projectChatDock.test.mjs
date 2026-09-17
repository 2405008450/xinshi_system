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
  assert.match(annotationPage, /\{ command: 'project-chat', label: '沟通' \}/)
  assert.match(annotationPage, /if \(command === 'project-chat'\)[\s\S]*openProjectChat\(row\)/)
  assert.doesNotMatch(annotationPage, /@click="openProjectChat\(row\)">沟通<\/el-button>/)
  assert.match(annotationPage, /projectType:\s*'annotation'/)
  assert.match(dock, /<Teleport to="body">/)
  assert.match(dock, /v-show="!chatWindow\.minimized"/)
  assert.match(dock, /minimizeChat\(chatWindow\.key\)/)
  assert.match(dock, /restoreChat\(chatWindow\.key\)/)
  assert.match(dock, /closeChat\(chatWindow\.key\)/)
  assert.match(dockStore, /MAX_EXPANDED_WINDOWS\s*=\s*3/)
  assert.match(dockStore, /oldest\.minimized\s*=\s*true/)
  assert.match(dockStore, /const closeAllChats = \(\) =>/)
  assert.match(dock, /closeAllChats\(\)/)
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

test('聊天窗支持独立定位、拖拽、置顶与视口边界约束', () => {
  assert.match(dockStore, /WINDOW_WIDTH\s*=\s*420/)
  assert.match(dockStore, /WINDOW_HEIGHT\s*=\s*640/)
  assert.match(dockStore, /VIEWPORT_MARGIN\s*=\s*8/)
  assert.match(dockStore, /const nextCascadePosition = \(\) =>/)
  assert.match(dockStore, /const clampPosition = \(x, y/)
  assert.match(dockStore, /const focusChat = \(key\) =>/)
  assert.match(dockStore, /const setPosition = \(key, x, y\) =>/)
  assert.match(dockStore, /const clampAllPositions = \(\) =>/)
  assert.match(dockStore, /const updateChatMeta = \(key, \{ title, subtitle \}/)
  assert.match(dockStore, /const incrementUnread = \(key\) =>/)
  assert.match(dockStore, /chatWindow\.unread = 0/)
  assert.match(dock, /cursor: grab/)
  assert.match(dock, /cursor: grabbing/)
  assert.match(dock, /startDrag\(\$event, chatWindow\)/)
  assert.match(dock, /event\.target\.closest\('\.project-chat-window__heading, \.project-chat-window__actions, button, a'\)/)
  assert.match(dock, /setPosition\(dragState\.key, event\.clientX - dragState\.offsetX, event\.clientY - dragState\.offsetY\)/)
  assert.match(dock, /window\.addEventListener\('resize', syncViewportState\)/)
  assert.match(dock, /focusChat\(chatWindow\.key\)/)
})

test('小屏幕下聊天窗单窗近全屏并自动最小化其他会话', () => {
  assert.match(dock, /COMPACT_SCREEN_WIDTH\s*=\s*768/)
  assert.match(dock, /const enforceSoloWindow = \(\) =>/)
  assert.match(dock, /project-chat-window--solo/)
  assert.match(dock, /if \(isCompactScreen\.value \|\| event\.button !== 0\) return/)
})

test('项目信息按 projectType:projectId 缓存并异步补全标题与订单号', () => {
  assert.match(dockStore, /const projectMetaCache = new Map\(\)/)
  assert.match(dockStore, /translation: getProject/)
  assert.match(dockStore, /annotation: getAnnotationProject/)
  assert.match(dockStore, /title: data\?\.projectName \|\| ''/)
  assert.match(dockStore, /subtitle: data\?\.orderNo \|\| ''/)
  assert.match(dockStore, /projectMetaCache\.set\(cacheKey, null\)/)
  assert.match(dockStore, /正在加载项目信息…/)
})

test('最小化会话在任务栏胶囊展示未读并在恢复时清零', () => {
  assert.match(dockStore, /if \(!chatWindow \|\| !chatWindow\.minimized\) return/)
  assert.match(dock, /chatWindow\.unread > 99 \? '99\+' : chatWindow\.unread/)
  assert.match(dock, /project-chat-task__unread/)
})

test('三类聊天通知统一打开聊天小窗且不再跳转页面', () => {
  assert.match(notificationBell, /CHAT_NOTIFICATION_TYPES = \['project_chat', 'project_chat_mention', 'annotation_project_chat_mention'\]/)
  assert.match(notificationBell, /const projectType = item\.related_project_type \|\| 'translation'/)
  assert.match(notificationBell, /const projectId = item\.related_entity_id \|\| item\.related_project_id/)
  assert.match(notificationBell, /openChat\(\{ projectId, projectType \}\)/)
  assert.match(notificationBell, /if \(!projectId\) return false/)
  assert.match(notificationBell, /if \(isChatNotification\(item\) && openChatNotification\(item\)\) return/)
})

test('提醒卡片改为白底轻阴影并提供独立关闭按钮与打开提示', () => {
  assert.match(notificationBell, /showClose: true/)
  assert.match(notificationBell, /点击打开沟通/)
  assert.match(notificationBell, /mention-notification__summary/)
  assert.match(notificationBell, /mention-notification__hint/)
  assert.doesNotMatch(notificationBell, /border: 2px solid var\(--el-color-warning\)/)
})

test('会话模式时间正序、左右气泡、日期分隔与系统消息居中', () => {
  assert.match(chatPanel, /conversationMode:\s*\{ type: Boolean, default: false \}/)
  assert.match(dock, /conversation-mode/)
  assert.match(chatPanel, /const conversationItems = computed\(\(\) =>/)
  assert.match(chatPanel, /chat-conversation-item--own/)
  assert.match(chatPanel, /chat-date-divider/)
  assert.match(chatPanel, /chat-system-message__bar/)
  assert.match(chatPanel, /chat-avatar/)
  assert.match(chatPanel, /messages\.value = \(Array\.isArray\(res\?\.items\) \? res\.items : \[\]\)\.slice\(\)\.reverse\(\)/)
})

test('会话模式滚动加载更早消息并保持锚点、底部跟随与新消息提示', () => {
  assert.match(chatPanel, /const loadEarlierMessages = async \(\) =>/)
  assert.match(chatPanel, /wrap\.scrollTop = wrap\.scrollHeight - prevHeight \+ prevTop/)
  assert.match(chatPanel, /const isConversationAtBottom = \(\) =>/)
  assert.match(chatPanel, /const scrollConversationToBottom = \(\) =>/)
  assert.match(chatPanel, /pendingNewCount\.value \+= 1/)
  assert.match(chatPanel, /chat-new-message-tip/)
  assert.match(chatPanel, /const mergeLatestConversationMessages = async \(\) =>/)
  assert.match(chatPanel, /@scroll="handleConversationScroll"/)
})

test('会话模式输入区支持 @ 多选标签、Enter 发送与发送禁用', () => {
  assert.match(chatPanel, /chat-composer__mention-tags/)
  assert.match(chatPanel, /const handleComposerKeydown = \(event\) =>/)
  assert.match(chatPanel, /event\.key !== 'Enter' \|\| event\.shiftKey \|\| event\.isComposing/)
  assert.match(chatPanel, /Enter 发送，Shift\+Enter 换行/)
  assert.match(chatPanel, /:disabled="sending \|\| \(!composer\.content\.trim\(\) && !composer\.attachments\.length\)"/)
  assert.match(chatPanel, /defineExpose\(\{ toggleFilters \}\)/)
})

test('悬浮窗中标注项目纯文本常开、笔译项目保留富文本并遵守沟通开关', () => {
  assert.match(dock, /:text-only="chatWindow\.projectType === 'annotation'"/)
  assert.match(dock, /:always-enabled="chatWindow\.projectType === 'annotation'"/)
  assert.match(dock, /@unread="incrementUnread\(chatWindow\.key\)"/)
})
