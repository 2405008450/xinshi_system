import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const dock = readFileSync(new URL('../src/components/chat/ProjectChatDock.vue', import.meta.url), 'utf8')
const dockStore = readFileSync(new URL('../src/composables/useProjectChatDock.js', import.meta.url), 'utf8')
const workspace = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')
const windowMenu = readFileSync(new URL('../src/components/chat/ChatWindowStateMenu.vue', import.meta.url), 'utf8')
const historyPanel = readFileSync(new URL('../src/components/chat/ChatHistorySearchPanel.vue', import.meta.url), 'utf8')
const annotationChat = readFileSync(new URL('../src/components/chat/ChatConversation.vue', import.meta.url), 'utf8')
const followedStore = readFileSync(new URL('../src/composables/useAnnotationFollowed.js', import.meta.url), 'utf8')
const chatPanel = readFileSync(new URL('../src/components/ProjectChatPanel.vue', import.meta.url), 'utf8')
const annotationPage = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const layout = readFileSync(new URL('../src/layout/index.vue', import.meta.url), 'utf8')
const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')
const realtimeSocket = readFileSync(new URL('../src/utils/realtimeSocket.js', import.meta.url), 'utf8')

// 隔离接口与浏览器存储，直接验证窗口状态转换，避免仅靠源码匹配漏掉还原和缩放回归。
function createDockHarness(storage = new Map()) {
  const viewport = { innerWidth: 1440, innerHeight: 950 }
  const source = dockStore.replace(/^import .*\r?\n/gm, '').replace(/export const /g, 'const ')
  const { dock: instance, size, visible } = runInNewContext(`${source}\n;({ dock: useProjectChatDock(), size: resolveChatSize, visible: isChatWindowVisible })`, {
    reactive: value => value,
    getProject: async () => ({ projectName: '笔译项目', orderNo: 'T-001' }),
    getAnnotationProject: async () => ({ projectName: '标注项目', orderNo: 'A-001' }),
    window: viewport,
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    console,
  })
  return { dock: instance, size, visible, viewport, storage }
}

function workspaceVisibility(state, followedItems = [{ projectId: 'followed-project' }]) {
  const source = dock.slice(dock.indexOf('const workspaceVisible = computed'), dock.indexOf('const minimizedWindows = computed'))
  return runInNewContext(`${source}\n;({ visible: workspaceVisible.value, task: showWorkspaceTask.value })`, {
    state,
    followed: { value: followedItems },
    computed: getter => ({ get value() { return getter() } }),
  })
}

test('旧版全屏偏好刷新后恢复普通布局，已关注项目不会自动打开窗口', () => {
  for (const maximizedFrom of ['float', 'workspace', undefined]) {
    const storage = new Map([['xinshi.chatDock.anonymous', JSON.stringify({
      layout: 'workspace', workspaceMaximized: true, maximizedFrom,
      workspaceSize: 'large', sizeByType: { annotation: 'medium' },
    })]])
    const { dock: instance } = createDockHarness(storage)
    instance.ensurePreferences()
    assert.equal(instance.state.layout, maximizedFrom || 'float')
    assert.equal(instance.state.workspaceMaximized, false)
    assert.equal(instance.state.workspaceSize, 'large')
    assert.equal(workspaceVisibility(instance.state).visible, false)
    assert.equal(workspaceVisibility(instance.state).task, false)
    instance.openChat({ projectId: '1', projectType: 'annotation', title: '项目一', subtitle: 'A-001' })
    assert.equal(instance.state.windows[0].sizeMode, 'medium')
    assert.equal(instance.state.workspaceMaximized, false)
  }
})

test('主动全屏在本次会话内正常打开和恢复，刷新不继承全屏状态', () => {
  for (const layoutMode of ['float', 'workspace']) {
    const { dock: instance, storage } = createDockHarness()
    instance.setLayout(layoutMode)
    instance.openFullscreen()
    assert.equal(workspaceVisibility(instance.state).visible, true)
    instance.minimizeWorkspace()
    assert.equal(workspaceVisibility(instance.state).visible, false)
    assert.equal(workspaceVisibility(instance.state).task, true)
    instance.restoreWorkspace()
    assert.equal(instance.state.workspaceMaximized, true)
    const saved = JSON.parse(storage.get('xinshi.chatDock.anonymous'))
    assert.equal(saved.layout, layoutMode)
    assert.equal(saved.workspaceMaximized, undefined)
    const { dock: reloaded } = createDockHarness(storage)
    reloaded.ensurePreferences()
    assert.equal(reloaded.state.layout, layoutMode)
    assert.equal(reloaded.state.workspaceMaximized, false)
    assert.equal(workspaceVisibility(reloaded.state).visible, false)
    assert.equal(workspaceVisibility(reloaded.state).task, false)
    instance.closeAllChats()
    assert.equal(workspaceVisibility(instance.state).visible, false)
  }
})

test('全屏还原保留独立窗口位置与尺寸，最小化恢复保持当前会话', () => {
  const { dock: instance, size, viewport } = createDockHarness()
  const key = instance.openChat({ projectId: '1', title: '项目一', subtitle: 'A-001' })
  const chat = instance.state.windows[0]
  const original = { x: chat.x, y: chat.y, sizeMode: chat.sizeMode }
  instance.toggleWorkspaceMaximize()
  assert.equal(instance.state.layout, 'workspace')
  assert.equal(instance.state.workspaceX, 0)
  assert.equal(size('maximized').width, 1440)
  instance.minimizeWorkspace()
  instance.restoreWorkspace()
  assert.equal(instance.state.workspaceMaximized, true)
  assert.equal(instance.state.activeKey, key)
  instance.toggleWorkspaceMaximize()
  assert.equal(instance.state.layout, 'float')
  assert.deepEqual({ x: chat.x, y: chat.y, sizeMode: chat.sizeMode }, original)
  instance.toggleWorkspaceMaximize()
  viewport.innerWidth = 1024
  viewport.innerHeight = 720
  instance.clampAllPositions()
  assert.equal(size('maximized').width, 1024)
  assert.equal(size('maximized').height, 720)
  instance.toggleWorkspaceMaximize()
  assert.equal(instance.state.layout, 'float')
  assert.equal(chat.sizeMode, original.sizeMode)
  assert.ok(chat.x >= 8 && chat.x + size(chat.sizeMode).width <= 1024)
})

test('工作区全屏还原恢复拖动坐标，会话切换保留窗口实例', () => {
  const { dock: instance } = createDockHarness()
  const first = instance.openChat({ projectId: '1', title: '项目一', subtitle: 'A-001' })
  const second = instance.openChat({ projectId: '2', title: '项目二', subtitle: 'A-002' })
  const originalWindow = instance.state.windows[0]
  instance.setLayout('workspace')
  instance.setWorkspacePosition(100, 80)
  instance.toggleWorkspaceMaximize()
  instance.selectSession(first)
  instance.selectSession(second)
  assert.equal(instance.state.windows[0], originalWindow)
  instance.toggleWorkspaceMaximize()
  assert.equal(instance.state.layout, 'workspace')
  assert.equal(instance.state.workspaceX, 100)
  assert.equal(instance.state.workspaceY, 80)
  assert.equal(instance.state.workspaceSize, 'medium')
})

test('项目沟通 Dock 全局挂载并支持多窗、最小化和关闭', () => {
  assert.match(layout, /<ProjectChatDock(?:\s|>)/)
  assert.match(annotationPage, /\{ command: 'project-chat', label: '沟通' \}/)
  assert.match(annotationPage, /if \(command === 'project-chat'\)[\s\S]*openProjectChat\(row\)/)
  assert.doesNotMatch(annotationPage, /@click="openProjectChat\(row\)">沟通<\/el-button>/)
  assert.match(annotationPage, /projectType:\s*'annotation'/)
  assert.match(dock, /<Teleport to="body">/)
  assert.match(dock, /v-show="isChatWindowVisible\(chatWindow\)/)
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
  assert.match(chatPanel, /subscribe\('chat_message_acknowledgement', handleRealtimeChatAcknowledgement\)/)
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
  assert.match(dockStore, /const nextCascadePosition = \(mode = 'small'\) =>/)
  assert.match(dockStore, /const clampPosition = \(x, y/)
  assert.match(dockStore, /const focusChat = \(key, minimumZ = 0\) =>/)
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
  assert.match(dockStore, /if \(!chatWindow \|\| isChatWindowVisible\(chatWindow\)\) return/)
  assert.match(dock, /chatWindow\.unread > 99 \? '99\+' : chatWindow\.unread/)
  assert.match(dock, /project-chat-task__unread/)
})

test('聊天通知和群邀请统一打开聊天小窗且不再跳转页面', () => {
  assert.match(notificationBell, /CHAT_NOTIFICATION_TYPES = \['project_chat', 'project_chat_mention', 'annotation_project_chat_mention', 'annotation_project_chat_invite'\]/)
  assert.match(notificationBell, /const projectType = item\.related_project_type \|\| 'translation'/)
  assert.match(notificationBell, /const projectId = item\.related_entity_id \|\| item\.related_project_id/)
  assert.match(notificationBell, /openChat\(\{ projectId, projectType, messageId \}\)/)
  assert.match(notificationBell, /if \(!projectId\) return false/)
  assert.match(notificationBell, /if \(isChatNotification\(item\) && await openChatNotification\(item\)\) return/)
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
  assert.match(chatPanel, /:disabled="sending \|\| imagesBlocked \|\| \(!composer\.content\.trim\(\) && !pendingImages\.length\)"/)
  assert.match(chatPanel, /defineExpose\(\{ toggleFilters, openSearch, locateMessage, locate: locateMessage \}\)/)
})

test('沟通窗口支持小中大三档、会话列表布局，并按用户记住选择', () => {
  assert.match(dockStore, /sizeMode/)
  assert.match(dockStore, /medium: \{ width: 760, height: 680 \}/)
  assert.match(dockStore, /Math\.min\(1180, Math\.round\(viewportWidth \* 0\.94\)\)/)
  assert.match(dockStore, /Math\.min\(880, Math\.round\(viewportHeight \* 0\.92\)\)/)
  assert.match(dockStore, /xinshi\.chatDock\./)
  assert.match(dockStore, /sizeByType/)
  assert.match(dockStore, /const cycleSize = \(key\) =>/)
  assert.match(dockStore, /const toggleQuickSize = \(key\) =>/)
  assert.match(dockStore, /const setLayout = \(layout\) =>/)
  assert.match(dockStore, /workspaceSize === 'medium' \? 'large' : 'medium'/)
  assert.match(dockStore, /mode === 'maximized'/)
  assert.match(dockStore, /const toggleWorkspaceMaximize = \(\) =>/)
  assert.match(windowMenu, /aria-label="窗口状态"/)
  assert.match(windowMenu, /全屏聊天/)
  assert.match(workspace, /还原窗口/)
  assert.match(windowMenu, /会话工作区/)
  assert.match(dock, /v-if="!isCompactScreen"/)
  assert.match(dock, /project-chat-window--embedded/)
  assert.match(dock, /project-chat-window--medium :deep\(\.group-bubble\)/)
  assert.match(dock, /<span>沟通<\/span>/)
  assert.match(workspace, /消息/)
  assert.match(workspace, /未读/)
  assert.match(workspace, /setTimeout\(applyKeyword, 400\)/)
  assert.match(workspace, /if \(!value\)/)
  assert.match(followedStore, /chatRequest\('sessions', \{ signal: controller\.signal \}\)/)
  assert.match(followedStore, /setInterval\(refresh, 15000\)/)
  assert.match(historyPanel, /全部/)
  assert.match(historyPanel, /图片/)
  assert.match(historyPanel, /链接/)
  assert.match(historyPanel, /文件/)
  assert.match(historyPanel, /setTimeout\(\(\) => runSearch\(\), 400\)/)
  assert.match(historyPanel, /new AbortController\(\)/)
  assert.match(historyPanel, /if \(version !== generation\) return/)
  assert.match(historyPanel, /if \(!value\) runSearch\(\)/)
  assert.match(historyPanel, /allowFiles/)
  assert.match(annotationChat, /ChatHistorySearchPanel/)
  assert.match(annotationChat, /allow-files/)
  assert.match(annotationChat, /defineExpose\(\{ openSearch, locate, toggleFilters: openSearch \}\)/)
  assert.match(chatPanel, /const locateMessage = async/)
  assert.match(chatPanel, /返回最新消息/)
  assert.match(chatPanel, /around: messageId/)
})

test('悬浮窗中标注项目纯文本常开、笔译项目保留富文本并遵守沟通开关', () => {
  assert.match(dock, /:text-only="chatWindow\.projectType === 'annotation'"/)
  assert.match(dock, /:always-enabled="chatWindow\.projectType === 'annotation'"/)
  assert.match(dock, /@unread="incrementUnread\(chatWindow\.key\)"/)
})

test('顶栏可直接打开空会话大屏，多次点击保持大屏打开', () => {
  const { dock: instance } = createDockHarness()
  instance.openFullscreen()
  assert.equal(instance.state.workspaceOpened, true)
  assert.equal(instance.state.workspaceMaximized, true)
  instance.openFullscreen()
  assert.equal(instance.state.workspaceMaximized, true)
  instance.minimizeWorkspace()
  instance.openFullscreen()
  assert.equal(instance.state.workspaceMinimized, false)
  assert.match(layout, /aria-label="聊天大屏"/)
})

test('固定小窗只显示当前会话，重新进入大屏再还原不展开其他窗口', () => {
  const { dock: instance, visible } = createDockHarness()
  const first = instance.openChat({ projectId: '1', title: '项目一', subtitle: 'A-001' })
  const second = instance.openChat({ projectId: '2', title: '项目二', subtitle: 'A-002' })
  instance.minimizeChat(first)
  instance.openFullscreen()
  instance.pinChat(second)
  assert.equal(instance.state.layout, 'float')
  assert.equal(instance.state.pinnedKey, second)
  assert.equal(instance.state.windows.length, 2)
  assert.equal(instance.state.windows[0].minimized, true)
  assert.deepEqual(instance.state.windows.filter(visible).map(item => item.key).join(','), second)
  instance.focusChat(second, 5000)
  assert.ok(instance.state.windows.find(item => item.key === second).zIndex > 5000)
  instance.openFullscreen()
  const third = instance.openChat({ projectId: '3', title: '项目三', subtitle: 'A-003' })
  instance.selectSession(first)
  instance.toggleWorkspaceMaximize()
  assert.equal(instance.state.pinnedKey, second)
  assert.equal(instance.state.windows.find(item => item.key === first).minimized, true)
  assert.equal(instance.state.windows.find(item => item.key === third).minimized, true)
  assert.equal(instance.state.windows.find(item => item.key === second).minimized, false)
  assert.equal(instance.state.windows.filter(visible).map(item => item.key).join(','), second)
})
