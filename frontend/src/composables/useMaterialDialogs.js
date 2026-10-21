import { reactive, readonly } from 'vue'
import '@/styles/materialDialogs.css'

// 全局挂载，菜单与资料浮层销毁后，历史版本和回收站仍可独立使用。
const state = reactive({ loaded: false, historyOpen: false, historyRequest: null, trashOpen: false, trashProjectId: '' })
let serial = 0
export function useMaterialDialogs() {
  return {
    state: readonly(state),
    openHistory(projectId, file) {
      state.loaded = true
      state.historyRequest = { projectId, fileId: file.file_id, name: file.original_name, serial: ++serial }
      state.historyOpen = true
    },
    openTrash(projectId) { state.loaded = true; state.trashProjectId = projectId; state.trashOpen = true },
    closeHistory() { state.historyOpen = false },
    closeTrash() { state.trashOpen = false },
  }
}
