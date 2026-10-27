import { nextTick, reactive } from 'vue'
import { sessionListKey } from '@/utils/chatSessionList'
import { getProject } from '@/api/projects'
import { getAnnotationProject } from '@/api/annotationProjects'

const MAX_EXPANDED_WINDOWS = 6
const WINDOW_WIDTH = 420
const WINDOW_HEIGHT = 640
const VIEWPORT_MARGIN = 8
const CASCADE_STEP = 36
const DOCK_Z_BASE = 2100
const COMPACT_SCREEN_WIDTH = 768
const SIZE_MODES = ['small', 'medium', 'large']

let sequence = 0
let duplicateSequence = 0
let zSequence = DOCK_Z_BASE

const state = reactive({
  windows: [],
  closedSessionKeys: [],
  recentClosedSessions: [],
  layout: 'float',
  tileMode: '',
  workspaceMinimized: false,
  workspaceOpened: false,
  pinnedKey: '',
  workspaceSize: 'medium',
  workspaceMaximized: false,
  maximizedFrom: 'float',
  workspaceX: 0,
  workspaceY: 0,
  workspaceZ: DOCK_Z_BASE,
  workspaceReady: false,
  activeKey: '',
  preferencesReady: false,
  viewportWidth: typeof window === 'undefined' ? 1280 : window.innerWidth,
  viewportHeight: typeof window === 'undefined' ? 800 : window.innerHeight,
})

const sizePreference = { translation: 'small', annotation: 'small', direct: 'small' }
let maximizedRestoreX = 0
let maximizedRestoreY = 0
let maximizedRestoreReady = false
let floatWindowSnapshot = null
const projectMetaCache = new Map()
const projectMetaRequests = new Map()

const projectMetaLoaders = {
  translation: getProject,
  annotation: getAnnotationProject,
}

const preferenceStorageKey = () => {
  let userId = 'anonymous'
  try {
    userId = localStorage.getItem('user_id') || 'anonymous'
  } catch {
    userId = 'anonymous'
  }
  return `xinshi.chatDock.${userId}`
}

const normalizeSize = (value, fallback = 'small') => (SIZE_MODES.includes(value) ? value : fallback)

const normalizeWorkspaceSize = (value) => (value === 'large' ? 'large' : 'medium')

const persistPreferences = () => {
  try {
    localStorage.setItem(preferenceStorageKey(), JSON.stringify({
      // 全屏是本次打开的临时状态，只保存进入全屏前的布局。
      layout: state.workspaceMaximized ? state.maximizedFrom : state.layout,
      workspaceSize: state.workspaceSize,
      sizeByType: { ...sizePreference },
      closedSessionKeys: [...state.closedSessionKeys],
      recentClosedSessions: state.recentClosedSessions,
    }))
  } catch {
    // 隐私模式或存储配额不足时仍允许本次会话使用当前档位。
  }
}

const ensurePreferences = () => {
  if (state.preferencesReady) return
  state.preferencesReady = true
  try {
    const saved = JSON.parse(localStorage.getItem(preferenceStorageKey()) || '{}')
    state.closedSessionKeys = Array.isArray(saved.closedSessionKeys)
      ? [...new Set(saved.closedSessionKeys.filter(key => typeof key === 'string' && /^(annotation|translation|direct):.+$/.test(key)))] : []
    state.recentClosedSessions = Array.isArray(saved.recentClosedSessions) ? saved.recentClosedSessions.filter(item =>
      item && typeof item.key === 'string' && /^(annotation|translation|direct):.+$/.test(item.key) && typeof item.projectId === 'string').slice(0, 10) : []
    // 兼容旧版全屏偏好，刷新后恢复普通布局，不自动遮住业务页面。
    const savedLayout = saved.workspaceMaximized === true ? saved.maximizedFrom : saved.layout
    if (savedLayout === 'workspace' || savedLayout === 'float') state.layout = savedLayout
    state.workspaceSize = normalizeWorkspaceSize(saved.workspaceSize)
    if (saved.sizeByType && typeof saved.sizeByType === 'object') {
      sizePreference.translation = normalizeSize(saved.sizeByType.translation)
      sizePreference.annotation = normalizeSize(saved.sizeByType.annotation)
    }
    persistPreferences()
  } catch {
    state.layout = 'float'
  }
}

export const resolveChatSize = (mode = 'small') => {
  const viewportWidth = Number(state.viewportWidth) || 1280
  const viewportHeight = Number(state.viewportHeight) || 800
  if (mode === 'maximized') {
    return {
      width: viewportWidth,
      height: viewportHeight,
    }
  }
  const presets = {
    small: { width: WINDOW_WIDTH, height: WINDOW_HEIGHT },
    medium: { width: 760, height: 680 },
    large: {
      width: Math.min(1180, Math.round(viewportWidth * 0.94)),
      height: Math.min(880, Math.round(viewportHeight * 0.92)),
    },
  }
  const size = presets[normalizeSize(mode)] || presets.small
  return {
    width: Math.min(size.width, Math.max(320, viewportWidth - VIEWPORT_MARGIN * 2)),
    height: Math.min(size.height, Math.max(360, viewportHeight - VIEWPORT_MARGIN * 2)),
  }
}

export const isChatWindowVisible = (chatWindow) => {
  if (!chatWindow) return false
  if (state.layout === 'workspace' && state.workspaceMinimized) return false
  if (state.layout === 'workspace') return state.activeKey === chatWindow.key
  if (state.pinnedKey && state.pinnedKey !== chatWindow.key) return false
  return !chatWindow.minimized
}

const touchWindow = (chatWindow) => {
  sequence += 1
  chatWindow.lastActiveOrder = sequence
}

const enforceExpandedLimit = (preferredKey) => {
  if (state.layout === 'workspace') return
  const limit = state.tileMode === 'medium' ? 3 : MAX_EXPANDED_WINDOWS
  const oldestFirst = items => items.filter(item => item.key !== preferredKey).sort((a, b) => a.lastActiveOrder - b.lastActiveOrder)
  const medium = state.windows.filter(item => !item.minimized && item.sizeMode !== 'small')
  oldestFirst(medium).slice(0, Math.max(0, medium.length - 3)).forEach(item => { item.minimized = true })
  const expanded = state.windows.filter(item => !item.minimized)
  oldestFirst(expanded).slice(0, Math.max(0, expanded.length - limit)).forEach(item => { item.minimized = true })
}

const clampPosition = (x, y, width = WINDOW_WIDTH, height = WINDOW_HEIGHT) => {
  const viewportWidth = Math.max(Number(window.innerWidth) || 0, width + VIEWPORT_MARGIN * 2)
  const viewportHeight = Math.max(Number(window.innerHeight) || 0, height + VIEWPORT_MARGIN * 2)
  return {
    x: Math.min(Math.max(Number(x) || 0, VIEWPORT_MARGIN), viewportWidth - width - VIEWPORT_MARGIN),
    y: Math.min(Math.max(Number(y) || 0, VIEWPORT_MARGIN), viewportHeight - height - VIEWPORT_MARGIN),
  }
}

const workspaceFrameMode = () => (state.workspaceMaximized ? 'maximized' : state.workspaceSize)

const ensureWorkspacePlaced = () => {
  const size = resolveChatSize(workspaceFrameMode())
  if (state.workspaceMaximized) {
    state.workspaceX = 0
    state.workspaceY = 0
    state.workspaceReady = true
    return
  }
  if (!state.workspaceReady) {
    const viewportWidth = Number(window.innerWidth) || 1280
    const viewportHeight = Number(window.innerHeight) || 800
    Object.assign(state, {
      workspaceX: viewportWidth - size.width - 24,
      workspaceY: viewportHeight - size.height - 24,
      workspaceReady: true,
    })
  }
  const position = clampPosition(state.workspaceX, state.workspaceY, size.width, size.height)
  state.workspaceX = position.x
  state.workspaceY = position.y
}

// 新窗口从右下角开始阶梯排列，超出后回到起点重新错层。
const nextCascadePosition = (mode = 'small') => {
  const size = resolveChatSize(mode)
  const viewportWidth = Number(window.innerWidth) || 1280
  const viewportHeight = Number(window.innerHeight) || 800
  const maxOffset = Math.max(
    0,
    Math.min(viewportWidth - size.width, viewportHeight - size.height) - VIEWPORT_MARGIN * 2 - 48
  )
  const stepCount = Math.max(1, Math.floor(maxOffset / CASCADE_STEP))
  const index = state.windows.length % (stepCount + 1)
  const offset = Math.min(index * CASCADE_STEP, maxOffset)
  return clampPosition(
    viewportWidth - size.width - 24 - offset,
    viewportHeight - size.height - 24 - offset,
    size.width,
    size.height,
  )
}

const resolveProjectMeta = async (projectType, projectId, refresh = false) => {
  const cacheKey = `${projectType}:${projectId}`
  if (!refresh && projectMetaCache.has(cacheKey)) return projectMetaCache.get(cacheKey)
  if (!projectMetaRequests.has(cacheKey)) {
    const loader = projectMetaLoaders[projectType]
    if (!loader) return null
    projectMetaRequests.set(
      cacheKey,
      loader(projectId)
        .then((data) => {
          const meta = {
            title: data?.projectName || '',
            subtitle: data?.orderNo || '',
            projectStatus: data?.projectStatus || '',
          }
          projectMetaCache.set(cacheKey, meta)
          return meta
        })
        .catch((error) => {
          console.error('加载项目信息失败', error)
          projectMetaCache.set(cacheKey, null)
          return null
        })
        .finally(() => projectMetaRequests.delete(cacheKey))
    )
  }
  return projectMetaRequests.get(cacheKey)
}

const fillChatWindowMeta = async (chatWindow, refresh = false) => {
  if ((!refresh && chatWindow.metaLoaded) || chatWindow.metaLoading) return
  chatWindow.metaLoading = true
  const meta = await resolveProjectMeta(chatWindow.projectType, chatWindow.projectId, refresh)
  if (state.windows.includes(chatWindow)) {
    chatWindow.metaLoading = false
    chatWindow.metaLoaded = true
    if (meta) {
      chatWindow.title = meta.title || chatWindow.title
      chatWindow.subtitle = meta.subtitle
      chatWindow.projectStatus = meta.projectStatus
    } else if (chatWindow.title === '正在加载项目信息…') {
      // 项目信息加载失败（无权限或已删除）仍允许查看聊天。
      chatWindow.title = '项目沟通'
    }
  }
}

// 未关注但临时打开的项目不会进入会话接口，随已有刷新周期补齐其当前状态。
export const refreshOpenAnnotationStatuses = sessions => Promise.all(state.windows
  .filter(item => item.projectType === 'annotation' && !sessions.some(session => session.key === item.key))
  .map(item => fillChatWindowMeta(item, true)))

const focusWorkspace = () => {
  state.workspaceZ = ++zSequence
  const active = state.windows.find(item => item.key === state.activeKey)
  if (active) {
    active.zIndex = state.workspaceZ
    touchWindow(active)
  }
}

const activateWorkspace = (key) => {
  if (state.layout !== 'workspace') return
  state.workspaceMinimized = false
  state.activeKey = key
  ensureWorkspacePlaced()
  focusWorkspace()
}

const openChat = ({ projectId, projectType = 'translation', title = '', subtitle = '', messageId = '', projectStatus = '', allowDuplicate = false, syncSidebar = false }) => {
  if (!projectId) return null
  ensurePreferences()
  const announce=()=>syncSidebar&&nextTick(()=>{const active=state.windows.find(row=>row.key===state.activeKey);if(active?.projectType===projectType&&active?.projectId===String(projectId))window.dispatchEvent(new CustomEvent('chat-conversation-activated',{detail:{projectType,projectId:String(projectId)}}))})
  const conversationKey = `${projectType}:${projectId}`
  const key = allowDuplicate ? `${conversationKey}:copy-${++duplicateSequence}` : conversationKey
  state.recentClosedSessions = state.recentClosedSessions.filter(item => !(item.sessionKeys || [item.key]).includes(conversationKey))
  if (state.closedSessionKeys.includes(conversationKey)) {
    state.closedSessionKeys = state.closedSessionKeys.filter(item => item !== conversationKey)
    persistPreferences()
  }
  persistPreferences()
  const existing = !allowDuplicate && (state.windows.find(item => item.key === state.activeKey && item.projectType === projectType && item.projectId === String(projectId)) || state.windows.find(item => item.projectType === projectType && item.projectId === String(projectId)))
  if (existing) {
    if (messageId) existing.targetMessageId = messageId
    if (title) existing.title = title
    if (subtitle) existing.subtitle = subtitle
    if (projectStatus) existing.projectStatus = projectStatus
    existing.minimized = false
    if (state.layout === 'float' && state.tileMode) existing.sizeMode = state.tileMode
    if (state.pinnedKey && state.layout === 'float') state.pinnedKey = existing.key
    existing.unread = 0
    state.activeKey = existing.key
    focusChat(existing.key)
    activateWorkspace(existing.key)
    enforceExpandedLimit(existing.key)
    if (!title || !subtitle || (projectType === 'annotation' && !existing.projectStatus)) fillChatWindowMeta(existing, true)
    announce()
    return existing.key
  }

  const needsMeta = !['direct', 'discussion'].includes(projectType) && (!title || !subtitle || (projectType === 'annotation' && !projectStatus))
  const sizeMode = state.layout === 'float' && state.tileMode ? state.tileMode : normalizeSize(sizePreference[projectType])
  const chatWindow = reactive({
    key,
    conversationKey,
    projectId: String(projectId),
    projectType,
    accessConfirmed: false,
    projectStatus,
    targetMessageId: messageId,
    title: title || (needsMeta ? '正在加载项目信息…' : '项目沟通'),
    subtitle,
    minimized: false,
    unread: 0,
    lastActiveOrder: 0,
    zIndex: 0,
    x: 0,
    y: 0,
    sizeMode,
    metaLoading: false,
    metaLoaded: !needsMeta,
  })
  Object.assign(chatWindow, nextCascadePosition(sizeMode))
  touchWindow(chatWindow)
  chatWindow.zIndex = ++zSequence
  state.activeKey = key
  state.windows.push(chatWindow)
  if (state.pinnedKey && state.layout === 'float') state.pinnedKey = key
  activateWorkspace(key)
  enforceExpandedLimit(key)
  if (needsMeta) fillChatWindowMeta(chatWindow)
  announce()
  return key
}

const focusChat = (key, minimumZ = 0) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  state.activeKey = key
  zSequence = Math.max(zSequence, Number(minimumZ) || 0)
  chatWindow.zIndex = ++zSequence
  touchWindow(chatWindow)
}

const updateChatMeta = (key, { title, subtitle } = {}) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  if (title) chatWindow.title = title
  if (subtitle !== undefined) chatWindow.subtitle = subtitle
}

const setPosition = (key, x, y) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  const size = resolveChatSize(chatWindow.sizeMode || 'small')
  Object.assign(chatWindow, clampPosition(x, y, size.width, size.height))
}

const setWorkspacePosition = (x, y) => {
  if (state.workspaceMaximized) return
  const size = resolveChatSize(state.workspaceSize)
  const position = clampPosition(x, y, size.width, size.height)
  state.workspaceX = position.x
  state.workspaceY = position.y
  state.workspaceReady = true
}

const applySize = (chatWindow, mode) => {
  const next = normalizeSize(mode)
  chatWindow.sizeMode = next
  if (chatWindow.projectType === 'translation' || chatWindow.projectType === 'annotation') {
    sizePreference[chatWindow.projectType] = next
  }
  persistPreferences()
  const size = resolveChatSize(next)
  Object.assign(chatWindow, clampPosition(chatWindow.x, chatWindow.y, size.width, size.height))
  enforceExpandedLimit(chatWindow.key)
}

const cycleSize = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  const index = SIZE_MODES.indexOf(chatWindow.sizeMode || 'small')
  applySize(chatWindow, SIZE_MODES[(index + 1) % SIZE_MODES.length])
}

const setSize = (key, mode) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (chatWindow) { applySize(chatWindow, mode); enforceExpandedLimit(key) }
}

const setWorkspaceSize = (mode) => {
  state.workspaceSize = normalizeWorkspaceSize(mode)
  state.workspaceMaximized = false
  persistPreferences()
  ensureWorkspacePlaced()
}

const rememberFloatWindows = () => {
  if (state.layout !== 'float') return
  floatWindowSnapshot = new Map(state.windows.map(item => [item.key, item.minimized]))
}

const restoreFloatWindows = () => {
  if (!floatWindowSnapshot) return
  state.windows.forEach(item => {
    // 大屏里新开的会话先收起，避免退出时突然铺开一批窗口。
    item.minimized = floatWindowSnapshot.has(item.key) ? floatWindowSnapshot.get(item.key) : true
  })
  floatWindowSnapshot = null
}

const toggleQuickSize = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  applySize(chatWindow, chatWindow.sizeMode === 'medium' ? 'small' : 'medium')
}

const cycleWorkspaceSize = () => {
  if (state.workspaceMaximized) state.workspaceMaximized = false
  else state.workspaceSize = state.workspaceSize === 'medium' ? 'large' : 'medium'
  persistPreferences()
  ensureWorkspacePlaced()
}

const toggleWorkspaceMaximize = () => {
  ensurePreferences()
  if (state.workspaceMaximized) {
    state.workspaceMaximized = false
    const restoreLayout = state.maximizedFrom === 'workspace' ? 'workspace' : 'float'
    state.layout = restoreLayout
    persistPreferences()
    if (restoreLayout === 'workspace') {
      state.workspaceX = maximizedRestoreX
      state.workspaceY = maximizedRestoreY
      state.workspaceReady = maximizedRestoreReady
      state.workspaceMinimized = false
      ensureWorkspacePlaced()
      focusWorkspace()
      return
    }
    restoreFloatWindows()
    const active = state.windows.find(item => item.key === state.activeKey)
    if (active && isChatWindowVisible(active)) {
      active.unread = 0
      focusChat(active.key)
    }
    enforceExpandedLimit(state.activeKey)
    return
  }
  rememberFloatWindows()
  state.maximizedFrom = state.layout === 'workspace' ? 'workspace' : 'float'
  maximizedRestoreX = state.workspaceX
  maximizedRestoreY = state.workspaceY
  maximizedRestoreReady = state.workspaceReady
  state.workspaceMaximized = true
  state.layout = 'workspace'
  state.workspaceOpened = true
  state.workspaceMinimized = false
  if (!state.windows.some(item => item.key === state.activeKey)) {
    const newest = [...state.windows].sort((left, right) => right.lastActiveOrder - left.lastActiveOrder)[0]
    state.activeKey = newest?.key || ''
  }
  const active = state.windows.find(item => item.key === state.activeKey)
  if (active) active.unread = 0
  ensureWorkspacePlaced()
  focusWorkspace()
  persistPreferences()
}

const openFullscreen = () => {
  ensurePreferences()
  if (!state.workspaceMaximized) toggleWorkspaceMaximize()
  state.layout = 'workspace'
  state.workspaceOpened = true
  state.workspaceMinimized = false
  ensureWorkspacePlaced()
  focusWorkspace()
}

const pinChat = (key = state.activeKey) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  state.tileMode = ''
  restoreFloatWindows()
  state.layout = 'float'
  state.workspaceMaximized = false
  state.workspaceMinimized = false
  state.pinnedKey = key
  chatWindow.minimized = false
  applySize(chatWindow, 'small')
  focusChat(key)
  persistPreferences()
}

const setLayout = (layout) => {
  ensurePreferences()
  if (layout === 'workspace') rememberFloatWindows()
  state.layout = layout === 'workspace' ? 'workspace' : 'float'
  if (state.layout === 'float') state.workspaceMaximized = false
  persistPreferences()
  if (state.layout === 'workspace') {
    state.workspaceOpened = true
    state.workspaceMinimized = false
    if (!state.windows.some(item => item.key === state.activeKey)) {
      const newest = [...state.windows].sort((left, right) => right.lastActiveOrder - left.lastActiveOrder)[0]
      state.activeKey = newest?.key || ''
    }
    ensureWorkspacePlaced()
    const active = state.windows.find(item => item.key === state.activeKey)
    if (active) active.unread = 0
    focusWorkspace()
    return
  }
  restoreFloatWindows()
  if (state.activeKey) {
    const active = state.windows.find(item => item.key === state.activeKey)
    if (active) {
      active.minimized = false
      active.unread = 0
      focusChat(state.activeKey)
    }
    enforceExpandedLimit(state.activeKey)
  }
}

const clampAllPositions = () => {
  // 视口异常（最小化到 0 或小于窗口尺寸）时保持原坐标，避免把窗口永久压到角落。
  const viewportWidth = Number(window.innerWidth) || 0
  const viewportHeight = Number(window.innerHeight) || 0
  // 视口尺寸参与 Vue 响应式计算，全屏及聊天内容区随缩放一起更新。
  if (viewportWidth > 0) state.viewportWidth = viewportWidth
  if (viewportHeight > 0) state.viewportHeight = viewportHeight
  if (state.workspaceReady) ensureWorkspacePlaced()
  if (
    viewportWidth < WINDOW_WIDTH + VIEWPORT_MARGIN * 2
    || viewportHeight < WINDOW_HEIGHT + VIEWPORT_MARGIN * 2
  ) return
  state.windows.forEach((chatWindow) => {
    const size = resolveChatSize(chatWindow.sizeMode || 'small')
    Object.assign(chatWindow, clampPosition(chatWindow.x, chatWindow.y, size.width, size.height))
  })
}

const incrementUnread = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow || isChatWindowVisible(chatWindow)) return
  chatWindow.unread += 1
}

const rememberClosedSession = (session, sessionKeys = [session.key]) => {
  if (!session?.key || session.projectType === 'discussion' || session.key.startsWith('discussion:')) return
  const entry = {
    key: session.key, projectId: String(session.projectId || session.key.slice(session.key.indexOf(':') + 1)),
    projectType: session.projectType || session.kind || session.key.split(':')[0],
    title: session.title || session.subtitle || '未命名会话', subtitle: session.subtitle || '',
    projectStatus: session.projectStatus || '', categoryIds: session.categoryIds || [], sessionKeys,
  }
  const previous = state.recentClosedSessions.filter(item => sessionListKey(item) === sessionListKey(entry))
  entry.sessionKeys = [...new Set([...sessionKeys, ...previous.flatMap(item => item.sessionKeys || [item.key])])]
  state.recentClosedSessions = [entry, ...state.recentClosedSessions.filter(item => sessionListKey(item) !== sessionListKey(entry))].slice(0, 10)
}

const closeChat = (key, { session, recordRecent = true } = {}) => {
  if (!key) return
  ensurePreferences()
  const closing = state.windows.find(item => item.key === key)
  const conversationKey = closing?.conversationKey || key
  const hasAnother = state.windows.some(item => item.key !== key && (item.conversationKey || item.key) === conversationKey)
  if (!conversationKey.startsWith('discussion:') && !hasAnother) {
    if (recordRecent) rememberClosedSession({ ...(session || closing || { key }), key: conversationKey }, [conversationKey])
    if (!state.closedSessionKeys.includes(conversationKey)) state.closedSessionKeys.push(conversationKey)
  }
  persistPreferences()
  const index = state.windows.findIndex(item => item.key === key)
  if (index >= 0) state.windows.splice(index, 1)
  if (state.pinnedKey === key) state.pinnedKey = '__empty__'
  if (state.activeKey === key) {
    const newest = [...state.windows].sort((left, right) => right.lastActiveOrder - left.lastActiveOrder)[0]
    state.activeKey = newest?.key || ''
  }
}

const closeSessionEntry = (session) => {
  ensurePreferences()
  if (session.projectType === 'discussion') return
  const keys = session.catalogKeys || [session.key]
  rememberClosedSession(session, keys)
  for (const key of keys) {
    const windows = state.windows.filter(item => (item.conversationKey || item.key) === key)
    if (windows.length) for (const item of windows) closeChat(item.key, { recordRecent: false })
    else closeChat(key, { recordRecent: false })
  }
}

const revealSession = (session) => {
  ensurePreferences()
  const keys = session.sessionKeys || [session.key]
  state.closedSessionKeys = state.closedSessionKeys.filter(key => !keys.includes(key))
  state.recentClosedSessions = state.recentClosedSessions.filter(item => !(item.sessionKeys || [item.key]).some(key => keys.includes(key)))
  persistPreferences()
}
const restoreClosedSession = (session) => {
  revealSession(session)
  const key = openChat(session)
  persistPreferences()
  return key
}

const syncClosedSessionCatalog = (catalog) => {
  ensurePreferences()
  if (state.recentClosedSessions.length || !catalog.length) return
  const known = new Set(state.recentClosedSessions.flatMap(item => item.sessionKeys || [item.key]))
  // 为升级前只记录了 ID 的关闭项补齐名称，不改变原有关闭顺序。
  for (const key of state.closedSessionKeys) {
    if (known.has(key)) continue
    const session = catalog.find(item => item.key === key)
    if (session) rememberClosedSession({ ...session, projectType: session.projectType || session.kind })
  }
  persistPreferences()
}

const closeAllChats = () => {
  state.tileMode = ''
  state.windows.splice(0, state.windows.length)
  state.activeKey = ''
  state.pinnedKey = ''
  state.workspaceOpened = false
}

const closeWorkspaceSession = () => {
  if (!state.activeKey) return
  if (state.activeKey) closeChat(state.activeKey)
  state.workspaceOpened = true
  state.workspaceMinimized = false
}

const minimizeChat = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (chatWindow) chatWindow.minimized = true
}

const minimizeWorkspace = () => {
  state.workspaceMinimized = true
}

const restoreWorkspace = () => {
  state.workspaceMinimized = false
  const active = state.windows.find(item => item.key === state.activeKey) || state.windows[0]
  if (active) {
    state.activeKey = active.key
    active.unread = 0
    focusChat(active.key)
  }
  if (state.layout === 'workspace') ensureWorkspacePlaced()
}

const selectSession = (key) => {
  const chatWindow = state.windows.find(item => item.key === key) || state.windows.find(item => item.conversationKey === key)
  if (!chatWindow) return
  chatWindow.minimized = false
  chatWindow.unread = 0
  state.workspaceMinimized = false
  focusChat(chatWindow.key)
  if (state.layout === 'workspace') ensureWorkspacePlaced()
}

const restoreChat = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  chatWindow.minimized = false
  if (state.pinnedKey) state.pinnedKey = key
  chatWindow.unread = 0
  focusChat(key)
  enforceExpandedLimit(key)
}

const openTiledSessions = (sessions, mode = 'small') => {
  const unique = [...new Map(sessions.map(item => [`${item.projectType || item.kind}:${item.projectId}`, item])).values()]
  const limit = mode === 'medium' ? 3 : 6
  if (!unique.length || unique.length > limit) return false
  ensurePreferences()
  floatWindowSnapshot = null
  state.layout = 'float'; state.tileMode = mode === 'medium' ? 'medium' : 'small'
  state.workspaceMaximized = false; state.workspaceOpened = false; state.pinnedKey = ''
  const keys = unique.map(item => openChat({ ...item, projectType: item.projectType || item.kind }))
  state.windows.forEach(item => { item.minimized = !keys.includes(item.key); if (!item.minimized) item.sizeMode = state.tileMode })
  state.activeKey = keys[0]
  persistPreferences()
  return true
}

const exitTiling = () => { state.tileMode = ''; setLayout('workspace') }

const duplicateChat = (key = state.activeKey) => {
  const source = state.windows.find(item => item.key === key)
  if (!source || !['annotation', 'translation'].includes(source.projectType)) return null
  floatWindowSnapshot = null
  state.layout = 'float'; state.tileMode = source.sizeMode === 'medium' ? 'medium' : 'small'
  state.workspaceMaximized = false; state.workspaceOpened = false; state.pinnedKey = ''; source.minimized = false
  return openChat({ projectId: source.projectId, projectType: source.projectType, title: source.title, subtitle: source.subtitle, projectStatus: source.projectStatus, allowDuplicate: true })
}

export const useProjectChatDock = () => ({
  revealSession,
  openTiledSessions,
  exitTiling,
  duplicateChat,
  state,
  openChat,
  closeChat,
  closeSessionEntry,
  restoreClosedSession,
  syncClosedSessionCatalog,
  closeAllChats,
  closeWorkspaceSession,
  minimizeChat,
  restoreChat,
  focusChat,
  focusWorkspace,
  updateChatMeta,
  setPosition,
  setWorkspacePosition,
  clampAllPositions,
  incrementUnread,
  cycleSize,
  setSize,
  setWorkspaceSize,
  pinChat,
  openFullscreen,
  toggleQuickSize,
  cycleWorkspaceSize,
  toggleWorkspaceMaximize,
  setLayout,
  selectSession,
  minimizeWorkspace,
  restoreWorkspace,
  ensurePreferences,
  ensureWorkspacePlaced,
})

export const PROJECT_CHAT_WINDOW_SIZE = { width: WINDOW_WIDTH, height: WINDOW_HEIGHT }
export const PROJECT_CHAT_COMPACT_WIDTH = COMPACT_SCREEN_WIDTH
