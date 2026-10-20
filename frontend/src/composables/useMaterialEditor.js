import { reactive, readonly } from 'vue'

// 在线编辑弹窗挂在公共布局上：资料浮层或详情小窗关闭后，编辑中的内容仍然保留。
const state = reactive({ loaded: false, open: false, request: null, savedTicks: {} })
let serial = 0

export function useMaterialEditor() {
  // request: { projectId, file }（编辑已有版本）或 { projectId, create: { kind, name, folderId } }
  const openMaterialEditor = request => {
    if (state.open) return false
    state.request = { ...request, serial: ++serial }
    state.loaded = true; state.open = true
    return true
  }
  const closeMaterialEditor = () => { state.open = false; state.request = null }
  // 同一项目的资料组件监听计数后刷新列表，不依赖打开编辑器的组件是否仍然挂载。
  const notifyMaterialSaved = projectId => { state.savedTicks[projectId] = (state.savedTicks[projectId] || 0) + 1 }
  return { state: readonly(state), openMaterialEditor, closeMaterialEditor, notifyMaterialSaved }
}
