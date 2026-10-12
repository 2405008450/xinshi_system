import { reactive } from 'vue'

const state = reactive({ collapsed: false, expanded: [] })
let identity = ''
export const topicNavigationKey = userId => `xinshi.chatTopics.navigation.${userId || 'anonymous'}`
export function parseTopicNavigation(value) {
  if (!value || typeof value.collapsed !== 'boolean' || !Array.isArray(value.expanded)) throw new Error('主题导航配置无效')
  return { collapsed: value.collapsed, expanded: [...new Set(value.expanded.filter(id => typeof id === 'string'))] }
}
export function useChatTopicNavigation() {
  let userId = ''
  try { userId = localStorage.getItem('user_id') || '' } catch { /* 存储不可用时使用内存状态。 */ }
  const key = topicNavigationKey(userId)
  if (key !== identity) {
    identity = key
    Object.assign(state, { collapsed: false, expanded: [] })
    try {
      const raw = localStorage.getItem(key)
      if (raw) Object.assign(state, parseTopicNavigation(JSON.parse(raw)))
    } catch { try { localStorage.removeItem(key) } catch { /* 存储不可用时使用默认状态。 */ } }
  }
  function persist() { try { localStorage.setItem(key, JSON.stringify(state)) } catch { /* 本次展开状态仍生效。 */ } }
  function toggleCollapsed() { state.collapsed = !state.collapsed; persist() }
  function toggleRoot(id) { state.expanded = state.expanded.includes(id) ? state.expanded.filter(value => value !== id) : [...state.expanded, id]; persist() }
  function cleanRoots(ids) {
    const valid = state.expanded.filter(id => ids.includes(id))
    if (valid.length !== state.expanded.length) { state.expanded = valid; persist() }
  }
  return { navigation: state, toggleCollapsed, toggleRoot, cleanRoots }
}
