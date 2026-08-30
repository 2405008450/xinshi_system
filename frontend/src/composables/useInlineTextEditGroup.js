import { ref } from 'vue'

// 详情小窗之间共享当前编辑器，确保任一时刻只允许操作一个自由文本字段。
export const activeInlineTextEditorId = ref('')
