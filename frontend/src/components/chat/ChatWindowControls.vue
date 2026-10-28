<template>
  <div class="chat-fixed-window-controls" @mousedown.stop @dblclick.stop>
    <ChatProjectEntry v-if="showEntry" :project-id="projectId" :project-type="projectType" @navigate="emit('navigate')" />
    <button v-if="showSearch" type="button" aria-label="聊天记录" title="聊天记录" @click="emit('search')"><el-icon><Search /></el-icon></button>
    <template v-if="showResize">
      <button type="button" class="chat-window-control--first" aria-label="最小化会话窗口" title="最小化" @click="emit('minimize')"><el-icon><Minus /></el-icon></button>
      <button v-if="!maximized" type="button" aria-label="最大化会话窗口" title="最大化" @click="emit('maximize')"><el-icon><FullScreen /></el-icon></button>
      <button v-else type="button" aria-label="还原会话窗口" title="还原窗口（正常大小）" @click="emit('restore')"><el-icon><CopyDocument /></el-icon></button>
    </template>
    <button v-if="showExit" type="button" class="chat-window-control--exit" aria-label="退出整个会话窗口" title="退出整个会话窗口，保留聊天记录" @click.stop="emit('exit')"><el-icon><Close /></el-icon></button>
  </div>
</template>

<script setup>
import { Close, CopyDocument, FullScreen, Minus, Search } from '@element-plus/icons-vue'
import ChatProjectEntry from './ChatProjectEntry.vue'

defineProps({
  projectId: { type: String, default: '' },
  projectType: { type: String, default: '' },
  showEntry: { type: Boolean, default: true },
  showSearch: { type: Boolean, default: true },
  showResize: { type: Boolean, default: true },
  showExit: { type: Boolean, default: true },
  maximized: { type: Boolean, default: false }
})
const emit = defineEmits(['navigate', 'search', 'minimize', 'maximize', 'restore', 'exit'])
</script>

<style scoped>
.chat-fixed-window-controls{display:flex;align-items:center;gap:4px;height:var(--chat-control-h,32px);background:#fff}
.chat-fixed-window-controls>button,.chat-fixed-window-controls :deep(.el-button){position:relative;display:inline-flex;align-items:center;justify-content:center;flex:none;box-sizing:border-box;width:var(--chat-control-h,32px);min-width:var(--chat-control-h,32px);height:var(--chat-control-h,32px);min-height:var(--chat-control-h,32px);margin:0;padding:0;border:1px solid transparent;border-radius:var(--chat-radius,6px);background:transparent;color:var(--chat-text-muted,#64748b);cursor:pointer}
.chat-fixed-window-controls>button:hover,.chat-fixed-window-controls :deep(.el-button:hover){background:var(--chat-hover-bg,#f1f5f9);border-color:var(--chat-border,#e2e8f0);color:var(--chat-text,#334155)}
.chat-fixed-window-controls>button:focus-visible,.chat-fixed-window-controls :deep(.el-button:focus-visible){outline:2px solid var(--color-primary,#334155);outline-offset:1px}
.chat-fixed-window-controls :deep(.el-button>span){display:inline-flex;align-items:center;justify-content:center}
.chat-fixed-window-controls .el-icon,.chat-fixed-window-controls :deep(.el-icon){width:var(--chat-icon-size,16px);height:var(--chat-icon-size,16px);font-size:var(--chat-icon-size,16px)!important;line-height:1}
.chat-fixed-window-controls>button.chat-window-control--first{margin-left:6px}
.chat-fixed-window-controls>button.chat-window-control--exit:hover{background:var(--chat-danger-bg,#fee2e2);border-color:var(--chat-danger-border,#fecaca);color:var(--chat-danger,#dc2626)}
</style>
