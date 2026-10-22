import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { filterClosedSessions, sessionListKey, mentionUnreadCount } from '../src/utils/chatSessionList.js'
import { chatTileLayout } from '../src/utils/chatTiling.js'

const dock = readFileSync(new URL('../src/components/chat/ProjectChatDock.vue', import.meta.url), 'utf8')
const dockStore = readFileSync(new URL('../src/composables/useProjectChatDock.js', import.meta.url), 'utf8')
const workspace = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')
const windowMenu = readFileSync(new URL('../src/components/chat/ChatWindowStateMenu.vue', import.meta.url), 'utf8')
const historyPanel = readFileSync(new URL('../src/components/chat/ChatHistorySearchPanel.vue', import.meta.url), 'utf8')
const annotationChat = readFileSync(new URL('../src/components/chat/ChatConversation.vue', import.meta.url), 'utf8')
const followedStore = readFileSync(new URL('../src/composables/useAnnotationFollowed.js', import.meta.url), 'utf8')
const chatPanel = readFileSync(new URL('../src/components/ProjectChatPanel.vue', import.meta.url), 'utf8')
const favorites = readFileSync(new URL('../src/components/chat/AnnotationChatInbox.vue', import.meta.url), 'utf8')
const managersSummary = readFileSync(new URL('../src/components/chat/ChatProjectManagersSummary.vue', import.meta.url), 'utf8')
const annotationPage = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const layout = readFileSync(new URL('../src/layout/index.vue', import.meta.url), 'utf8')
const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')
const chatNotifications = readFileSync(new URL('../src/composables/useChatNotifications.js', import.meta.url), 'utf8')
const realtimeSocket = readFileSync(new URL('../src/utils/realtimeSocket.js', import.meta.url), 'utf8')

// 隔离接口与浏览器存储，直接验证窗口状态转换，避免仅靠源码匹配漏掉还原和缩放回归。
function createDockHarness(storage = new Map(), annotationLoader = async () => ({ projectName: '标注项目', orderNo: 'A-001', projectStatus: 'trial_preparation' })) {
  const viewport = { innerWidth: 1440, innerHeight: 950 }
  const source = dockStore.replace(/^import .*\r?\n/gm, '').replace(/export const /g, 'const ')
  const { dock: instance, size, visible, refreshStatuses } = runInNewContext(`${source}\n;({ dock: useProjectChatDock(), size: resolveChatSize, visible: isChatWindowVisible, refreshStatuses: refreshOpenAnnotationStatuses })`, {
    reactive: value => value,
    sessionListKey,
    getProject: async () => ({ projectName: '笔译项目', orderNo: 'T-001' }),
    getAnnotationProject: annotationLoader,
    window: viewport,
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    console,
  })
  return { dock: instance, size, visible, viewport, storage, refreshStatuses }
}

test('临时标注会话即使已有名称也补齐状态，并在后续刷新时读取当前状态', async () => {
  let status = 'trial_preparation', calls = 0
  const h = createDockHarness(new Map(), async () => { calls++; return { projectName: '测试项目', orderNo: 'A-001', projectStatus: status } })
  h.dock.openChat({ projectId: '1', projectType: 'annotation', title: '测试项目', subtitle: 'A-001' })
  for (let i = 0; i < 10; i++) await Promise.resolve()
  assert.equal(h.dock.state.windows[0].projectStatus, 'trial_preparation')
  status = 'client_feedback'
  await h.refreshStatuses([])
  assert.equal(h.dock.state.windows[0].projectStatus, 'client_feedback')
  assert.equal(calls, 2)
  await h.refreshStatuses([{ key: 'annotation:1' }])
  assert.equal(calls, 2)
  h.dock.closeAllChats()
})

function workspaceVisibility(state, followedItems = [{ projectId: 'followed-project' }]) {
  const source = dock.slice(dock.indexOf('const workspaceVisible = computed'), dock.indexOf('const minimizedWindows = computed'))
  return runInNewContext(`${source}\n;({ visible: workspaceVisible.value, task: showWorkspaceTask.value })`, {
    state,
    followed: { value: followedItems },
    computed: getter => ({ get value() { return getter() } }),
  })
}

test('关闭会话按当前用户记住移出状态，刷新后不复现，从项目重新打开可恢复', () => {
  const storage = new Map()
  const first = createDockHarness(storage).dock
  const key = first.openChat({ projectId: 'parent', projectType: 'annotation', title: '测试项目', subtitle: 'AP-261007-001', projectStatus: 'trial_preparation' })
  first.closeChat(key)
  assert.equal(first.state.windows.length, 0)
  assert.equal(first.state.activeKey, '')
  assert.deepEqual(Array.from(first.state.closedSessionKeys), [key])
  const second = createDockHarness(storage).dock
  second.ensurePreferences()
  assert.deepEqual(Array.from(second.state.closedSessionKeys), [key])
  second.openChat({ projectId: 'parent', projectType: 'annotation', title: '测试项目', subtitle: 'AP-261007-001', projectStatus: 'trial_preparation' })
  assert.deepEqual(Array.from(second.state.closedSessionKeys), [])
  assert.equal(second.state.windows.length, 1)
})

test('关闭未打开的目录会话仍可移出，重复关闭不会新增记录', () => {
  const { dock: instance } = createDockHarness()
  instance.closeChat('annotation:catalog-only')
  instance.closeChat('annotation:catalog-only')
  assert.deepEqual(Array.from(instance.state.closedSessionKeys), ['annotation:catalog-only'])
  assert.equal(instance.state.windows.length, 0)
})

test('最近关闭按关闭顺序保留10个系列，重复关闭前移，点击恢复仅打开目标订单', () => {
  const { dock: instance, storage } = createDockHarness()
  const sessions = Array.from({ length: 12 }, (_, i) => ({ key: `annotation:${i}`, projectId: String(i), projectType: 'annotation', title: `会话${i}`, subtitle: `AP-261021-${String(i + 1).padStart(3, '0')}`, projectStatus: 'trial_preparation' }))
  for (const session of sessions) instance.closeSessionEntry(session)
  assert.equal(instance.state.recentClosedSessions.length, 10)
  assert.equal(instance.state.recentClosedSessions[0].key, 'annotation:11')
  instance.closeSessionEntry(sessions[5])
  assert.equal(instance.state.recentClosedSessions[0].key, 'annotation:5')
  assert.equal(new Set(instance.state.recentClosedSessions.map(row => row.key)).size, 10)
  const restored = createDockHarness(storage).dock
  restored.ensurePreferences()
  assert.equal(restored.state.recentClosedSessions.length, 10)
  restored.restoreClosedSession(restored.state.recentClosedSessions[0])
  assert.deepEqual(Array.from(restored.state.windows, row => row.key), ['annotation:5'])
  assert.equal(restored.state.recentClosedSessions.length, 9)
  assert.equal(restored.state.closedSessionKeys.includes('annotation:5'), false)
})

test('资源讨论自动恢复旧关闭项，后续关闭窗口不会移出列表或加入最近关闭', () => {
  const storage = new Map([['xinshi.chatDock.anonymous', JSON.stringify({ closedSessionKeys: ['discussion:resource', 'annotation:a'], recentClosedSessions: [{ key: 'discussion:resource', projectId: 'resource', projectType: 'discussion' }] })]])
  const { dock: instance } = createDockHarness(storage)
  instance.ensurePreferences()
  assert.deepEqual(Array.from(instance.state.closedSessionKeys), ['annotation:a'])
  assert.equal(instance.state.recentClosedSessions.length, 0)
  instance.openChat({ projectId: 'resource', projectType: 'discussion', title: '资源讨论' })
  instance.closeChat('discussion:resource')
  assert.equal(instance.state.windows.length, 0)
  assert.equal(instance.state.closedSessionKeys.includes('discussion:resource'), false)
  assert.equal(instance.state.recentClosedSessions.length, 0)
})

test('主子订单先后关闭合成一条最近记录，恢复入口但只打开最后关闭的订单', () => {
  const { dock: instance } = createDockHarness()
  const parent = { key: 'annotation:p', projectId: 'p', projectType: 'annotation', title: '主订单', subtitle: 'AP-261021-001', projectStatus: 'trial_preparation' }
  const child = { key: 'annotation:c', projectId: 'c', projectType: 'annotation', title: '子订单', subtitle: 'AP-261021-001.001', projectStatus: 'trial_preparation' }
  instance.closeSessionEntry(parent)
  assert.equal(instance.state.recentClosedSessions.length, 1)
  instance.closeSessionEntry(child)
  assert.equal(instance.state.recentClosedSessions.length, 1)
  assert.deepEqual(new Set(instance.state.recentClosedSessions[0].sessionKeys), new Set([parent.key, child.key]))
  instance.restoreClosedSession(instance.state.recentClosedSessions[0])
  assert.deepEqual(Array.from(instance.state.windows, row => row.key), [child.key])
  assert.equal(instance.state.closedSessionKeys.length, 0)
})

test('从主订单或子订单发起聊天只创建该订单窗口，异步补齐资料和打开大屏不创建关联订单窗口', async () => {
  for (const [projectId, orderNo] of [['parent', 'AP-261007-001'], ['child', 'AP-261007-001.001']]) {
    const requested = []
    const { dock: instance } = createDockHarness(new Map(), async id => {
      requested.push(id)
      return { projectName: '同名项目', orderNo, projectStatus: 'trial_preparation', parentProjectId: projectId === 'child' ? 'parent' : null }
    })
    const key = instance.openChat({ projectId, projectType: 'annotation', title: '同名项目', subtitle: orderNo })
    for (let i = 0; i < 10; i++) await Promise.resolve()
    instance.openFullscreen()
    assert.deepEqual(Array.from(instance.state.windows, row => row.projectId), [projectId])
    assert.deepEqual(requested, [projectId])
    assert.equal(instance.state.activeKey, key)
    instance.closeAllChats()
  }
})

test('群聊和单聊关闭当前会话，最后一个关闭后保留大屏，由退出按钮单独退出', () => {
  for (const projectType of ['annotation', 'direct']) {
    const { dock: instance, visible } = createDockHarness()
    const key = instance.openChat({ projectId: 'close-me', projectType, title: '待关闭会话', subtitle: '测试' })
    instance.openFullscreen()
    assert.equal(visible(instance.state.windows[0]), true)
    instance.closeWorkspaceSession()
    assert.equal(instance.state.windows.some(row => row.key === key), false)
    assert.equal(instance.state.activeKey, '')
    assert.equal(workspaceVisibility(instance.state).visible, true)
    assert.equal(workspaceVisibility(instance.state).task, false)
    instance.openFullscreen()
    instance.closeWorkspaceSession()
    assert.equal(workspaceVisibility(instance.state).visible, true)
    instance.closeAllChats()
    assert.equal(workspaceVisibility(instance.state).visible, false)
  }
})

test('关闭当前会话不删除其他已打开会话；减号仍只最小化', () => {
  const { dock: instance } = createDockHarness()
  const first = instance.openChat({ projectId: 'group', projectType: 'annotation', title: '群聊', subtitle: 'A-001' })
  const second = instance.openChat({ projectId: 'person', projectType: 'direct', title: '单聊', subtitle: '客户部' })
  instance.openFullscreen()
  instance.closeWorkspaceSession()
  assert.deepEqual(Array.from(instance.state.windows, row => row.key), [first])
  assert.equal(instance.state.activeKey, first)
  assert.notEqual(instance.state.activeKey, second)
  assert.equal(workspaceVisibility(instance.state).visible, true)
  instance.minimizeWorkspace()
  assert.equal(instance.state.windows.length, 1)
  assert.equal(workspaceVisibility(instance.state).task, true)
  assert.match(workspace, /@click.stop="emit\('close-active'\)"/)
  assert.match(dock, /@close-active="closeWorkspaceSession"/)
})

test('一键恢复跨分组最新十项，恢复时列表变化也不跳项，最新会话成为当前项', () => {
  const { dock: instance } = createDockHarness()
  for (let i = 0; i < 12; i++) {
    const key = instance.openChat({ projectId: String(i), projectType: i % 2 ? 'annotation' : 'direct', title: `会话${i}` })
    instance.closeChat(key)
  }
  const latest = instance.state.recentClosedSessions[0].key
  const source = workspace.slice(workspace.indexOf('function restoreAllRecent()'), workspace.indexOf('const recentInFolder'))
  runInNewContext(`${source};restoreAllRecent()`, {
    props: { get recentClosed() { return instance.state.recentClosedSessions } },
    recentClosedVisible: { value: true },
    emit: (event, item) => instance.restoreClosedSession(item),
  })
  assert.equal(instance.state.windows.length, 10)
  assert.equal(instance.state.recentClosedSessions.length, 0)
  assert.equal(instance.state.activeKey, latest)
  assert.equal(instance.state.closedSessionKeys.length, 2)
})

test('历史提及只标记原目录及临时打开的项目，不能加入目录外项目', () => {
  const source = dock.slice(dock.indexOf('const sessions = computed'), dock.indexOf('async function updatePreference'))
  const rows = runInNewContext(`${source}\n;sessions.value`, {
    onMounted: () => {}, onBeforeUnmount: () => {},
    filterClosedSessions,
    computed: getter => ({ get value() { return getter() } }),
    followed: { value: [
      { key: 'annotation:a', kind: 'annotation', projectId: 'a' },
      { key: 'annotation:b', kind: 'annotation', projectId: 'b' },
      { key: 'direct:d', kind: 'direct', projectId: 'd' },
    ] },
    state: { windows: [{ key: 'annotation:temp', projectType: 'annotation', projectId: 'temp' }] },
    annotationMentionCounts: { value: [{ projectId: 'a', count: 3 }, { projectId: 'outside', count: 5 }, { projectId: 'temp', count: 2 }] },
  })
  assert.deepEqual(Array.from(rows, row => row.key), ['annotation:a', 'annotation:b', 'direct:d', 'annotation:temp'])
  assert.deepEqual(Array.from(rows, row => row.mentionHistoryCount), [3, 0, 0, 2])
  assert.deepEqual(Array.from(rows.filter(row => row.mentionHistoryCount > 0), row => row.projectId), ['a', 'temp'])
})

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
  assert.match(dock, /v-show="chatWindow.accessConfirmed !== false && isChatWindowVisible\(chatWindow\)/)
  assert.match(dock, /minimizeChat\(chatWindow\.key\)/)
  assert.match(dock, /restoreChat\(chatWindow\.key\)/)
  assert.match(dock, /closeChat\(chatWindow\.key\)/)
  assert.match(dockStore, /MAX_EXPANDED_WINDOWS\s*=\s*6/)
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

test('最小化任务只展示未读提及数字，普通未读继续在内部保留用于会话圆点', () => {
  assert.match(dockStore, /if \(!chatWindow \|\| isChatWindowVisible\(chatWindow\)\) return/)
  assert.match(dock, /chatWindow\.mentionUnread > 99 \? '99\+' : chatWindow\.mentionUnread/)
  assert.doesNotMatch(dock, /v-if="chatWindow\.unread"/)
  assert.match(dock, /project-chat-task__unread/)
})

test('聊天通知和群邀请统一打开聊天小窗且不再跳转页面', () => {
  assert.match(chatNotifications, /const projectId = item\.related_entity_id \|\| item\.related_project_id/)
  assert.match(chatNotifications, /openChat\(\{ projectId, projectType, messageId \}\)/)
  assert.match(chatNotifications, /if \(!projectId\)/)
  assert.match(dock, /useChatNotifications\(\)/)
  assert.doesNotMatch(notificationBell, /openChatNotification/)
})

test('提醒卡片改为白底轻阴影并提供独立关闭按钮与打开提示', () => {
  assert.match(chatNotifications, /showClose: true/)
  assert.match(chatNotifications, /点击打开沟通/)
  assert.match(chatNotifications, /mention-notification__summary/)
  assert.match(chatNotifications, /mention-notification__hint/)
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
  assert.match(annotationChat, /defineExpose\(\{ openSearch, locate, cancelLocate, toggleFilters: openSearch \}\)/)
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


test('@候选按群内与未参与分区，重名用户按 ID 保持独立且搜索不中断分区', () => {
  const segment = annotationChat.slice(annotationChat.indexOf('const mentionCandidates = computed'), annotationChat.indexOf('let mentionTrigger'))
  const group = {members:[{id:'a',name:'甲'}], eligibleUsers:[{id:'a',name:'甲'}], invitableUsers:[{id:'a',name:'甲'},{id:'b',name:'甲'},{id:'c',name:'乙'}]}
  const result = runInNewContext(segment+';mentionCandidates.value', {group, currentUserId:'self', computed:fn=>({value:fn()}),mentionQuery:{value:'甲'},matchesSearch:(name,query)=>name.includes(query)})
  assert.deepEqual(Array.from(result,row=>[row.id,row.outside]), [['a',false],['b',true]])
})


test('@候选在群内、群外和搜索结果中均排除本人，重名其他人仍可选择', () => {
  const segment = annotationChat.slice(annotationChat.indexOf('const mentionCandidates = computed'), annotationChat.indexOf('let mentionTrigger'))
  const group = { members: [{id: 1}], eligibleUsers: [{id: 1, name: '同名'}, {id: 2, name: '同名'}], invitableUsers: [{id: 1, name: '同名'}, {id: 3, name: '同名'}] }
  const result = runInNewContext(segment + ';mentionCandidates.value', {group, currentUserId: '1', computed: fn => ({value: fn()}), mentionQuery: {value: '同名'}, matchesSearch: (name, query) => name.includes(query)})
  assert.deepEqual(Array.from(result, row => row.id), [2, 3])
  const panelSegment = chatPanel.slice(chatPanel.indexOf('const mentionUserGroups = computed'), chatPanel.indexOf('const messages = ref'))
  const groups = runInNewContext(panelSegment + ';mentionUserGroups.value', {currentUserId: '1', userOptions: {value: group.eligibleUsers.concat({id: 3, name: '同名'})}, memberUserIds: {value: ['1', '2']}, computed: fn => ({value: fn()})})
  assert.deepEqual(Array.from(groups, section => Array.from(section.users, user => user.id)), [[2], [3]])
})

test('收藏项目名称和沟通按钮使用同一准确项目 ID，详情直接打开项目沟通', () => {
  const methods = favorites.slice(favorites.indexOf('function open(item)'), favorites.indexOf('watch(favoritesVisible'))
  const opened = [], routes = []
  const context = {favoritesVisible: {value: true}, openChat: item => opened.push(item), router: {push: target => routes.push(target)}}
  runInNewContext(methods + ';for (const item of [{projectId:"parent",orderNo:"AP-261007-001"},{projectId:"child",orderNo:"AP-261007-001.001"}]) {open(item);locateProject(item)}', context)
  assert.deepEqual(opened.map(item => item.projectId), ['parent', 'child'])
  assert.deepEqual(routes.map(item => item.query.projectId), ['parent', 'child'])
  assert.ok(routes.every(item => item.query.tab === 'chat' && !item.query.openProgress))
  assert.equal(context.favoritesVisible.value, false)
})

test('会话经理摘要保留多位及同名经理，按人员去重，空值和旧接口有合理回退', () => {
  const expressions = managersSummary.slice(managersSummary.indexOf('const clientManager = computed'), managersSummary.indexOf('let controller'))
  const evaluate = value => runInNewContext(expressions + ';({client:clientManager.value,names:names.value})', { project: { value }, computed: fn => ({get value() {return fn()}}) })
  const result = evaluate({clientManagerName:'客户负责人', roleAssignments:[
    {roleCode:'project_manager',assigneeId:'a',assigneeName:'同名'},
    {roleCode:'project_manager',assigneeId:'a',assigneeName:'同名'},
    {role_code:'project_manager',assignee_id:'b',assignee_name:'同名'},
    {roleCode:'reviewer',assigneeId:'c',assigneeName:'审校'},
  ]})
  assert.equal(result.client,'客户负责人')
  assert.deepEqual(Array.from(result.names),['同名','同名'])
  assert.equal(evaluate(null).client,'未设置')
  assert.deepEqual(Array.from(evaluate({clientManager:'客户经理',projectManagerName:'历史经理'}).names),['历史经理'])
})

test('平铺一次可打开六个小窗或三个中窗，超限不修改窗口，重复会话去重', () => {
  const { dock: instance } = createDockHarness()
  const items = Array.from({length:7},(_,i)=>({projectId:String(i),projectType:'annotation',title:`项目${i}`,subtitle:`AP-261022-00${i}`,projectStatus:'trial_preparation'}))
  assert.equal(instance.openTiledSessions(items,'small'),false)
  assert.equal(instance.state.windows.length,0)
  assert.equal(instance.openTiledSessions([...items.slice(0,6),items[0]],'small'),true)
  assert.equal(instance.state.layout,'float')
  assert.equal(instance.state.tileMode,'small')
  assert.equal(instance.state.windows.filter(item=>!item.minimized).length,6)
  assert.equal(instance.openTiledSessions(items.slice(0,4),'medium'),false)
  assert.equal(instance.state.tileMode,'small')
  assert.equal(instance.openTiledSessions(items.slice(0,3),'medium'),true)
  assert.equal(instance.state.windows.filter(item=>!item.minimized).length,3)
  assert.ok(instance.state.windows.filter(item=>!item.minimized).every(item=>item.sizeMode==='medium'))
  instance.exitTiling()
  assert.equal(instance.state.tileMode,'')
  assert.equal(instance.state.layout,'workspace')
})

test('平铺按屏幕调整列数，窄屏保留输入空间并允许内部滚动', () => {
  const wide=chatTileLayout(6,'small',1920,1080)
  assert.equal(wide.columns,3);assert.equal(wide.rows,2);assert.ok(wide.rowHeight>=400)
  assert.equal(chatTileLayout(3,'medium',1920,1080).columns,3)
  assert.equal(chatTileLayout(6,'small',700,871).columns,2)
  assert.equal(chatTileLayout(6,'small',375,800).columns,1)
  assert.equal(chatTileLayout(3,'medium',700,871).columns,1)
  assert.ok(chatTileLayout(6,'small',375,800).rowHeight>=400)
})

test('Tab 按窗口排列循环切换输入框，Shift+Tab 反向，其他字段与输入法不拦截', () => {
  const handler=dock.slice(dock.indexOf('function cycleComposer(event)'),dock.indexOf('const draggingKey'))
  const calls=[], keys=['a','b','c'], state={layout:'float'}
  const inputs=keys.map(key=>({disabled:false,getBoundingClientRect:()=>({width:300}),closest:()=>({style:{display:''},dataset:{chatKey:key}}),matches:()=>true,focus:()=>calls.push(`focus:${key}`),scrollIntoView:()=>{}}))
  const root={querySelectorAll:()=>inputs}
  const event={key:'Tab',target:inputs[0],currentTarget:root,preventDefault:()=>calls.push('prevent'),stopPropagation:()=>{}}
  const context={state,focusChat:key=>calls.push(key),event}
  runInNewContext(handler+';cycleComposer(event)',context)
  assert.deepEqual(calls,['prevent','b','focus:b'])
  calls.length=0;event.shiftKey=true
  runInNewContext(handler+';cycleComposer(event)',context)
  assert.deepEqual(calls,['prevent','c','focus:c'])
  calls.length=0;event.isComposing=true
  runInNewContext(handler+';cycleComposer(event)',context)
  assert.deepEqual(calls,[])
  event.isComposing=false;event.target={matches:()=>false}
  runInNewContext(handler+';cycleComposer(event)',context)
  assert.deepEqual(calls,[])
})

test('普通入口复用项目窗口，仅显式重复打开生成新窗口；关闭副本不关闭另一个窗口', () => {
  const { dock: instance } = createDockHarness()
  const input = {projectId:'same',projectType:'annotation',title:'同一项目',subtitle:'AP-261022-001',projectStatus:'trial_preparation'}
  const original = instance.openChat(input)
  assert.equal(instance.openChat(input),original)
  assert.equal(instance.state.windows.length,1)
  const duplicate = instance.duplicateChat(original)
  assert.notEqual(duplicate,original)
  assert.equal(instance.state.windows.length,2)
  assert.equal(instance.state.tileMode,'small')
  assert.equal(instance.openChat(input),duplicate)
  assert.equal(instance.state.windows.length,2)
  assert.ok(instance.state.windows.every(item=>item.projectId==='same' && item.conversationKey===original))
  instance.closeChat(original)
  assert.equal(instance.state.windows.length,1)
  assert.ok(!instance.state.closedSessionKeys.includes(original))
  assert.equal(instance.openChat(input),duplicate)
  instance.closeChat(duplicate)
  assert.deepEqual(Array.from(instance.state.closedSessionKeys),[original])
  assert.equal(instance.state.recentClosedSessions[0].key,original)
})

test('副本窗口不会生成重复会话列表项或重复计算未读提及', () => {
  const code=dock.slice(dock.indexOf('const sessions = computed'),dock.indexOf('function closeSessionGroup'))
  const original={key:'annotation:a',conversationKey:'annotation:a',projectId:'a',projectType:'annotation',mentionUnread:2,accessConfirmed:true}
  const copy={...original,key:'annotation:a:copy-1'}
  const rows=runInNewContext(code+';sessions.value',{state:{windows:[original,copy],closedSessionKeys:[]},followed:{value:[]},annotationMentionCounts:{value:[]},filterClosedSessions,computed:fn=>({get value(){return fn()}})})
  assert.equal(rows.length,1)
  assert.equal(rows[0].key,'annotation:a')
  assert.equal(mentionUnreadCount(rows),2)
})

test('收藏夹取消关注只修改当前订单关注状态，不退出会话；失败保留重试', async () => {
  const handler=favorites.slice(favorites.indexOf('async function unfollowFavorite()'),favorites.indexOf('watch(favoritesVisible'))
  const calls=[], messages=[], item={projectId:'child',orderNo:'AP-261007-001.001'}, context={
    favoriteMenuItem:{value:item},unfollowing:{value:false},favoriteMenuVisible:{value:true},
    annotationChatRequest:async(...args)=>calls.push(args),refresh:async()=>calls.push('refresh'),
    ElMessage:{success:text=>messages.push(text),error:text=>messages.push(text)},
  }
  await runInNewContext(handler+';unfollowFavorite()',context)
  assert.equal(calls[0][0],'child');assert.equal(calls[0][1],'following')
  assert.equal(calls[0][2].data.following,false)
  assert.equal(calls[1],'refresh');assert.equal(context.favoriteMenuVisible.value,false)
  assert.equal(context.unfollowing.value,false)
  context.favoriteMenuVisible.value=true;context.annotationChatRequest=async()=>{throw {detail:'连接失败'}}
  await runInNewContext(handler+';unfollowFavorite()',context)
  assert.equal(context.favoriteMenuVisible.value,true)
  assert.equal(context.unfollowing.value,false)
  assert.equal(messages.at(-1),'连接失败')
})

test('顶部聊天与侧栏共用未读提及口径，忽略普通未读并去除重复会话', () => {
  const rows=[{key:'a',unread:8,mentionUnread:2},{key:'a',unread:8,mentionUnread:2},{key:'b',unread:1,mentionUnread:0}]
  assert.equal(mentionUnreadCount(rows),2)
  assert.equal(mentionUnreadCount(filterClosedSessions(rows,['a'])),0)
})

test('顶部聊天等待窗口挂载后跳转 @我，零未读时进入消息面板', async () => {
  const method=layout.slice(layout.indexOf('async function openHeaderChat()'),layout.indexOf('const ResourceRequestDailyNotesDialog'))
  for(const count of [0,3]) {
    const events=[]
    await runInNewContext(method+';openHeaderChat()', {chatMentionTotal:{value:count},openFullscreen:()=>events.push('open'),nextTick:async()=>events.push('mounted'),chatEntryContext:()=>({}),route:{},CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail}},window:{dispatchEvent:event=>events.push(event)}})
    assert.equal(events[0],'open');assert.equal(events[1],'mounted')
    assert.equal(events[2].type,'chat-show-messages');assert.equal(events[2].detail.mentions,count>0)
  }
})
