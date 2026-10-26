<template>
  <el-popover v-model:visible="visible" trigger="click" placement="bottom-end" :width="244" popper-class="chat-window-state-menu">
    <template #reference>
      <el-button class="chat-window-state-trigger" size="small" aria-label="窗口大小" title="选择小窗、中窗或大窗">
        <el-icon><Operation /></el-icon><span v-if="!iconOnly">{{ maximized ? '大屏' : pinned ? '固定小窗' : '窗口' }}</span><el-icon v-if="!iconOnly"><ArrowDown /></el-icon>
      </el-button>
    </template>
    <div class="chat-window-state-menu__label">窗口大小</div>
    <div class="chat-window-state-menu__sizes">
      <el-button v-for="size in sizes" :key="size.key" size="small" :type="!maximized && sizeMode === size.key ? 'primary' : 'default'" :disabled="workspace && size.key === 'small'" @click="choose('resize', size.key)">{{ size.label }}</el-button>
    </div>
    <button v-if="!workspace" type="button" class="chat-window-state-menu__option" @click="choose('workspace')"><el-icon><ChatDotRound /></el-icon><span>会话工作区<small>在浮动窗口中切换会话</small></span></button>
  </el-popover>
</template>

<script setup>
import { ref } from 'vue'
import { ArrowDown, ChatDotRound, Operation } from '@element-plus/icons-vue'
defineProps({
  sizeMode: { type: String, default: 'small' },
  maximized: Boolean,
  iconOnly: Boolean,
  pinned: Boolean,
  workspace: Boolean,
  hasSession: { type: Boolean, default: true },
})
const emit = defineEmits(['resize', 'workspace'])
const visible = ref(false)
const sizes = [{ key: 'small', label: '小窗' }, { key: 'medium', label: '中窗' }, { key: 'large', label: '大窗' }]
const choose = (action, value) => { visible.value = false; emit(action, value) }
</script>

<style>
.chat-window-state-menu { max-width: calc(100vw - 24px); z-index: 100003 !important; }
</style>
<style scoped>
.chat-window-state-trigger { gap: 5px; }
.chat-window-state-menu__label { margin-bottom: 10px; color: var(--el-text-color-secondary); font-size: 12px; }
.chat-window-state-menu__sizes { display: flex; gap: 6px; margin-bottom: 10px; }
.chat-window-state-menu__sizes .el-button { flex: 1; margin: 0; }
.chat-window-state-menu__option { display: flex; width: 100%; gap: 10px; align-items: center; padding: 10px 8px; border: 0; border-radius: 6px; background: transparent; color: var(--el-text-color-primary); text-align: left; font: inherit; cursor: pointer; }
.chat-window-state-menu__option:hover, .chat-window-state-menu__option:focus-visible { background: var(--el-fill-color-light); }
.chat-window-state-menu__option:disabled { opacity: .5; cursor: not-allowed; }
.chat-window-state-menu__option span { display: flex; flex-direction: column; gap: 4px; }
.chat-window-state-menu__option small { color: var(--el-text-color-secondary); font-size: 12px; }
</style>
