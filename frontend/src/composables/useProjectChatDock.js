import { reactive } from 'vue'

const MAX_EXPANDED_WINDOWS = 3
let sequence = 0

const state = reactive({ windows: [] })

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

const openChat = ({ projectId, projectType = 'translation', title = '', subtitle = '' }) => {
  if (!projectId) return
  const key = `${projectType}:${projectId}`
  const existing = state.windows.find(item => item.key === key)
  if (existing) {
    existing.title = title || existing.title
    existing.subtitle = subtitle || existing.subtitle
    existing.minimized = false
    touchWindow(existing)
    enforceExpandedLimit(key)
    return
  }

  const chatWindow = reactive({
    key,
    projectId: String(projectId),
    projectType,
    title: title || '未命名项目',
    subtitle,
    minimized: false,
    lastActiveOrder: 0,
  })
  touchWindow(chatWindow)
  state.windows.push(chatWindow)
  enforceExpandedLimit(key)
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
  touchWindow(chatWindow)
  enforceExpandedLimit(key)
}

export const useProjectChatDock = () => ({
  state,
  openChat,
  closeChat,
  closeAllChats,
  minimizeChat,
  restoreChat,
})
