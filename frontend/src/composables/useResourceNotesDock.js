import { reactive, readonly } from 'vue'

// 单例状态随登录后的公共布局存活，不随业务页面切换销毁。
const state = reactive({ open: false, minimized: false })

export function useResourceNotesDock() {
  const openNotes = () => {
    state.open = true
    state.minimized = false
  }
  const minimizeNotes = () => {
    if (state.open) state.minimized = true
  }
  const closeNotes = () => {
    state.open = false
    state.minimized = false
  }
  return { state: readonly(state), openNotes, minimizeNotes, closeNotes }
}
