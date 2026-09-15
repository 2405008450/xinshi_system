import { reactive } from 'vue'
import { getProject } from '@/api/projects'
import { getAnnotationProject } from '@/api/annotationProjects'

const MAX_EXPANDED_WINDOWS = 3
const WINDOW_WIDTH = 420
const WINDOW_HEIGHT = 640
const VIEWPORT_MARGIN = 8
const CASCADE_STEP = 36
const DOCK_Z_BASE = 2100

let sequence = 0
let zSequence = DOCK_Z_BASE

const state = reactive({ windows: [] })

const projectMetaCache = new Map()
const projectMetaRequests = new Map()

const projectMetaLoaders = {
  translation: getProject,
  annotation: getAnnotationProject,
}

const touchWindow = (chatWindow) => {
  sequence += 1
  chatWindow.lastActiveOrder = sequence
}

const enforceExpandedLimit = (preferredKey) => {
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

// 新窗口从右下角开始阶梯排列，超出后回到起点重新错层。
const nextCascadePosition = () => {
  const viewportWidth = Number(window.innerWidth) || 1280
  const viewportHeight = Number(window.innerHeight) || 800
  const maxOffset = Math.max(
    0,
    Math.min(viewportWidth - WINDOW_WIDTH, viewportHeight - WINDOW_HEIGHT) - VIEWPORT_MARGIN * 2 - 48
  )
  const stepCount = Math.max(1, Math.floor(maxOffset / CASCADE_STEP))
  const index = state.windows.length % (stepCount + 1)
  const offset = Math.min(index * CASCADE_STEP, maxOffset)
  return clampPosition(
    viewportWidth - WINDOW_WIDTH - 24 - offset,
    viewportHeight - WINDOW_HEIGHT - 24 - offset
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

const openChat = ({ projectId, projectType = 'translation', title = '', subtitle = '' }) => {
  if (!projectId) return null
  const key = `${projectType}:${projectId}`
  const existing = state.windows.find(item => item.key === key)
  if (existing) {
    if (title) existing.title = title
    if (subtitle) existing.subtitle = subtitle
    existing.minimized = false
    existing.unread = 0
    focusChat(key)
    enforceExpandedLimit(key)
    if (!title || !subtitle) fillChatWindowMeta(existing)
    return key
  }

  const needsMeta = !title || !subtitle
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
    metaLoading: false,
    metaLoaded: !needsMeta,
  })
  Object.assign(chatWindow, nextCascadePosition())
  touchWindow(chatWindow)
  chatWindow.zIndex = ++zSequence
  state.windows.push(chatWindow)
  enforceExpandedLimit(key)
  if (needsMeta) fillChatWindowMeta(chatWindow)
  return key
}

const focusChat = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow) return
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
  Object.assign(chatWindow, clampPosition(x, y))
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
    Object.assign(chatWindow, clampPosition(chatWindow.x, chatWindow.y))
  })
}

const incrementUnread = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (!chatWindow || !chatWindow.minimized) return
  chatWindow.unread += 1
}

const closeChat = (key) => {
  const index = state.windows.findIndex(item => item.key === key)
  if (index >= 0) state.windows.splice(index, 1)
}

const closeAllChats = () => {
  state.windows.splice(0, state.windows.length)
}

const minimizeChat = (key) => {
  const chatWindow = state.windows.find(item => item.key === key)
  if (chatWindow) chatWindow.minimized = true
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
  updateChatMeta,
  setPosition,
  clampAllPositions,
  incrementUnread,
})

export const PROJECT_CHAT_WINDOW_SIZE = { width: WINDOW_WIDTH, height: WINDOW_HEIGHT }
