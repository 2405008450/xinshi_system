import { reactive } from 'vue'
import { getProject } from '@/api/projects'
import { getAnnotationProject } from '@/api/annotationProjects'

const MAX_EXPANDED_WINDOWS = 3
const WINDOW_WIDTH = 420
const WINDOW_HEIGHT = 640
const VIEWPORT_MARGIN = 8
const CASCADE_STEP = 36
const DOCK_Z_BASE = 2100
const COMPACT_SCREEN_WIDTH = 768
const SIZE_MODES = ['small', 'medium', 'large']

let sequence = 0
let zSequence = DOCK_Z_BASE

const state = reactive({
  windows: [],
  layout: 'float',
  workspaceMinimized: false,
  workspaceSize: 'medium',
  workspaceX: 0,
  workspaceY: 0,
  workspaceZ: DOCK_Z_BASE,
  workspaceReady: false,
  activeKey: '',
  preferencesReady: false,
})

const sizePreference = { translation: 'small', annotation: 'small' }
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
      layout: state.layout,
      workspaceSize: state.workspaceSize,
      sizeByType: { ...sizePreference },
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
    if (saved.layout === 'workspace' || saved.layout === 'float') state.layout = saved.layout
    state.workspaceSize = normalizeWorkspaceSize(saved.workspaceSize)
    if (saved.sizeByType && typeof saved.sizeByType === 'object') {
      sizePreference.translation = normalizeSize(saved.sizeByType.translation)
      sizePreference.annotation = normalizeSize(saved.sizeByType.annotation)
    }
  } catch {
    state.layout = 'float'
  }
}

export const resolveChatSize = (mode = 'small') => {
  const viewportWidth = typeof window === 'undefined' ? 1280 : (Number(window.innerWidth) || 1280)
  const viewportHeight = typeof window === 'undefined' ? 800 : (Number(window.innerHeight) || 800)
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
  return !chatWindow.minimized
}

const touchWindow = (chatWindow) => {
  sequence += 1
  chatWindow.lastActiveOrder = sequence
}

const enforceExpandedLimit = (preferredKey) => {
  if (state.layout === 'workspace') return
  const expanded = state.windows.filter(item => !item.minimized)
  if (expanded.length <= MAX_EXPANDED_WINDOWS) return
  const oldest = expanded
    .filter(item => item.key !== preferredKey)
    .sort((left, right) => left.lastActiveOrder - right.lastActiveOrder)[0]
  if (oldest) oldest.minimized = true
}

const clampPosition = (x, y, width = WINDOW_WIDTH, height = WINDOW_HEIGHT) => {
  const viewportWidth = Math.max(Number(window.innerWidth) || 0, width + VIEWPORT_MARGIN * 2)
  const viewportHeight = Math.max(Number(window.innerHeight) || 0, height + VIEWPORT_MARGIN * 2)
  return {
    x: Math.min(Math.max(Number(x) || 0, VIEWPORT_MARGIN), viewportWidth - width - VIEWPORT_MARGIN),
    y: Math.min(Math.max(Number(y) || 0, VIEWPORT_MARGIN), viewportHeight - height - VIEWPORT_MARGIN),
  }
}

const ensureWorkspacePlaced = () => {
  const size = resolveChatSize(state.workspaceSize)
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

const resolveProjectMeta = async (projectType, projectId) => {
  const cacheKey = `${projectType}:${projectId}`
  if (projectMetaCache.has(cacheKey)) return projectMetaCache.get(cacheKey)
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

const fillChatWindowMeta = async (chatWindow) => {
  if (chatWindow.metaLoaded || chatWindow.metaLoading) return
  chatWindow.metaLoading = true
  const meta = await resolveProjectMeta(chatWindow.projectType, chatWindow.projectId)
  if (state.windows.includes(chatWindow)) {
    chatWindow.metaLoading = false
    chatWindow.metaLoaded = true
    if (meta) {
      chatWindow.title = meta.title || chatWindow.title
      chatWindow.subtitle = meta.subtitle
    } else if (chatWindow.title === '正在加载项目信息…') {
      // 项目信息加载失败（无权限或已删除）仍允许查看聊天。
      chatWindow.title = '项目沟通'
    }
  }
}

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

const openChat = ({ projectId, projectType = 'translation', title = '', subtitle = '' }) => {
  if (!projectId) return null
  ensurePreferences()
  const key = `${projectType}:${projectId}`
  const existing = state.windows.find(item => item.key === key)
  if (existing) {
    if (title) existing.title = title
    if (subtitle) existing.subtitle = subtitle
    existing.minimized = false
    existing.unread = 0
    state.activeKey = key
    focusChat(key)
    activateWorkspace(key)
    enforceExpandedLimit(key)
    if (!title || !subtitle) fillChatWindowMeta(existing)
    return key
  }

  const needsMeta = !title || !subtitle
  const sizeMode = normalizeSize(sizePreference[projectType])
  const chatWindow = reactive({
    key,
    projectId: String(projectId),
    projectType,
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
  activateWorkspace(key)
  enforceExpandedLimit(key)
  if (needsMeta) fillChatWindowMeta(chatWindow)
  return key
}

const focusChat = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  state.activeKey = key
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
}

const cycleSize = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  const index = SIZE_MODES.indexOf(chatWindow.sizeMode || 'small')
  applySize(chatWindow, SIZE_MODES[(index + 1) % SIZE_MODES.length])
}

const toggleQuickSize = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  applySize(chatWindow, chatWindow.sizeMode === 'medium' ? 'small' : 'medium')
}

const cycleWorkspaceSize = () => {
  state.workspaceSize = state.workspaceSize === 'medium' ? 'large' : 'medium'
  persistPreferences()
  ensureWorkspacePlaced()
}

const setLayout = (layout) => {
  ensurePreferences()
  state.layout = layout === 'workspace' ? 'workspace' : 'float'
  persistPreferences()
  if (state.layout === 'workspace') {
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
  if (
    viewportWidth < WINDOW_WIDTH + VIEWPORT_MARGIN * 2
    || viewportHeight < WINDOW_HEIGHT + VIEWPORT_MARGIN * 2
  ) return
  state.windows.forEach((chatWindow) => {
    const size = resolveChatSize(chatWindow.sizeMode || 'small')
    Object.assign(chatWindow, clampPosition(chatWindow.x, chatWindow.y, size.width, size.height))
  })
  if (state.workspaceReady) ensureWorkspacePlaced()
}

const incrementUnread = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow || isChatWindowVisible(chatWindow)) return
  chatWindow.unread += 1
}

const closeChat = (key) => {
  const index = state.windows.findIndex(item => item.key === key)
  if (index >= 0) state.windows.splice(index, 1)
  if (state.activeKey === key) {
    const newest = [...state.windows].sort((left, right) => right.lastActiveOrder - left.lastActiveOrder)[0]
    state.activeKey = newest?.key || ''
  }
}

const closeAllChats = () => {
  state.windows.splice(0, state.windows.length)
  state.activeKey = ''
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
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  chatWindow.minimized = false
  chatWindow.unread = 0
  state.workspaceMinimized = false
  focusChat(key)
  if (state.layout === 'workspace') ensureWorkspacePlaced()
}

const restoreChat = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
  chatWindow.minimized = false
  chatWindow.unread = 0
  focusChat(key)
  enforceExpandedLimit(key)
}

export const useProjectChatDock = () => ({
  state,
  openChat,
  closeChat,
  closeAllChats,
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
  toggleQuickSize,
  cycleWorkspaceSize,
  setLayout,
  selectSession,
  minimizeWorkspace,
  restoreWorkspace,
  ensurePreferences,
  ensureWorkspacePlaced,
})

export const PROJECT_CHAT_WINDOW_SIZE = { width: WINDOW_WIDTH, height: WINDOW_HEIGHT }
export const PROJECT_CHAT_COMPACT_WIDTH = COMPACT_SCREEN_WIDTH
