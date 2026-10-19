import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 主题管理和会话分类共用编辑占用状态，避免两个入口同时留下名称草稿。
export const activeChatNameEditor = ref(null)
export function canStartChatNameEditing() {
  if (activeChatNameEditor.value !== null) {
    ElMessage.info('请先保存当前名称，或按 Esc 取消编辑')
    return false
  }
  return true
}
