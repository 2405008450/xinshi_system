<template>
  <Teleport to="body">
    <div v-if="state.windows.length || hasExtraTasks" class="project-chat-dock" aria-label="全局悬浮窗口">
      <section
        v-for="chatWindow in state.windows"
        v-show="!chatWindow.minimized"
        :key="chatWindow.key"
        class="project-chat-window"
        :class="{ 'project-chat-window--solo': isCompactScreen }"
        :style="windowStyle(chatWindow)"
        @mousedown="focusChat(chatWindow.key)"
      >
        <header
          class="project-chat-window__header"
          :class="{ 'project-chat-window__header--dragging': draggingKey === chatWindow.key }"
          @mousedown="startDrag($event, chatWindow)"
        >
          <div class="project-chat-window__heading">
            <div class="project-chat-window__title-row">
              <strong :title="chatWindow.title">{{ chatWindow.title }}</strong>
              <el-tag size="small" effect="plain" :type="chatWindow.projectType === 'annotation' ? 'success' : 'primary'">
                {{ chatWindow.projectType === 'annotation' ? '标注' : '笔译' }}
              </el-tag>
            </div>
            <span v-if="chatWindow.metaLoading" class="project-chat-window__subtitle">正在加载项目信息…</span>
            <span v-else-if="chatWindow.subtitle" class="project-chat-window__subtitle" :title="chatWindow.subtitle">
              {{ chatWindow.subtitle }}
            </span>
          </div>
          <div class="project-chat-window__actions">
            <el-button link aria-label="搜索消息" title="搜索消息" @click="toggleFilters(chatWindow.key)">
              <el-icon><Search /></el-icon>
            </el-button>
            <el-button link aria-label="最小化项目沟通" title="最小化" @click="minimizeChat(chatWindow.key)">
              <el-icon><Minus /></el-icon>
            </el-button>
            <el-button link aria-label="关闭项目沟通" title="关闭" @click="closeChat(chatWindow.key)">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </header>
        <div class="project-chat-window__body">
          <ProjectChatPanel
            :ref="(el) => setPanelRef(chatWindow.key, el)"
            :project-id="chatWindow.projectId"
            :project-type="chatWindow.projectType"
            :active="!chatWindow.minimized"
            conversation-mode
            compact
            :text-only="chatWindow.projectType === 'annotation'"
            :always-enabled="chatWindow.projectType === 'annotation'"
            @unread="incrementUnread(chatWindow.key)"
          />
        </div>
      </section>

      <div v-if="state.windows.some(item => item.minimized) || hasExtraTasks" class="project-chat-dock__taskbar">
        <div v-if="state.windows.some(item => item.minimized)" class="project-chat-dock__chat-tasks">
        <button
          v-for="chatWindow in state.windows.filter(item => item.minimized)"
          :key="chatWindow.key"
          type="button"
          class="project-chat-task"
          :title="`恢复 ${chatWindow.title}`"
          @click="restoreChat(chatWindow.key)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ chatWindow.title }}</span>
          <span v-if="chatWindow.subtitle" class="project-chat-task__subtitle">{{ chatWindow.subtitle }}</span>
          <span v-if="chatWindow.unread" class="project-chat-task__unread">
            {{ chatWindow.unread > 99 ? '99+' : chatWindow.unread }}
          </span>
        </button>
        </div>
        <slot name="tasks" />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChatDotRound, Close, Minus, Search } from '@element-plus/icons-vue'
import ProjectChatPanel from '@/components/ProjectChatPanel.vue'
import { useProjectChatDock, PROJECT_CHAT_WINDOW_SIZE } from '@/composables/useProjectChatDock'

defineProps({ hasExtraTasks: { type: Boolean, default: false } })

const {
  state,
  closeChat,
  closeAllChats,
  minimizeChat,
  restoreChat,
  focusChat,
  setPosition,
  clampAllPositions,
  incrementUnread,
} = useProjectChatDock()

const COMPACT_SCREEN_WIDTH = 768
const isCompactScreen = ref(false)
const draggingKey = ref('')
const panelRefs = new Map()

const setPanelRef = (key, el) => {
  if (el) panelRefs.set(key, el)
  else panelRefs.delete(key)
}

const toggleFilters = (key) => {
  focusChat(key)
  panelRefs.get(key)?.toggleFilters?.()
}

const windowStyle = (chatWindow) => {
  if (isCompactScreen.value) return { zIndex: chatWindow.zIndex }
  return {
    left: `${chatWindow.x}px`,
    top: `${chatWindow.y}px`,
    zIndex: chatWindow.zIndex,
  }
}

const dragState = { key: '', offsetX: 0, offsetY: 0 }

const handleDragMove = (event) => {
  if (!dragState.key) return
  setPosition(dragState.key, event.clientX - dragState.offsetX, event.clientY - dragState.offsetY)
}

const stopDrag = () => {
  dragState.key = ''
  draggingKey.value = ''
  window.removeEventListener('mousemove', handleDragMove)
  window.removeEventListener('mouseup', stopDrag)
}

// 仅标题栏空白区域作为拖拽手柄；项目名、订单号和按钮保留文字选择与点击。
const startDrag = (event, chatWindow) => {
  if (isCompactScreen.value || event.button !== 0) return
  if (event.target.closest('.project-chat-window__heading, .project-chat-window__actions, button, a')) return
  event.preventDefault()
  focusChat(chatWindow.key)
  dragState.key = chatWindow.key
  dragState.offsetX = event.clientX - chatWindow.x
  dragState.offsetY = event.clientY - chatWindow.y
  draggingKey.value = chatWindow.key
  window.addEventListener('mousemove', handleDragMove)
  window.addEventListener('mouseup', stopDrag)
}

// 小屏幕只保留最近使用的会话展开，其余自动最小化。
const enforceSoloWindow = () => {
  if (!isCompactScreen.value) return
  const expanded = state.windows
    .filter(item => !item.minimized)
    .sort((left, right) => right.lastActiveOrder - left.lastActiveOrder)
  expanded.slice(1).forEach((item) => { item.minimized = true })
}

const syncViewportState = () => {
  isCompactScreen.value = (Number(window.innerWidth) || 0) < COMPACT_SCREEN_WIDTH
  clampAllPositions()
  enforceSoloWindow()
}

watch(() => state.windows.length, () => {
  enforceSoloWindow()
})

onMounted(() => {
  syncViewportState()
  window.addEventListener('resize', syncViewportState)
})

onBeforeUnmount(() => {
  stopDrag()
  window.removeEventListener('resize', syncViewportState)
  closeAllChats()
})
</script>

<style scoped>
.project-chat-dock {
  position: fixed;
  inset: 0;
  z-index: 2100;
  pointer-events: none;
}

.project-chat-window {
  position: fixed;
  display: flex;
  width: v-bind('`${PROJECT_CHAT_WINDOW_SIZE.width}px`');
  height: v-bind('`${PROJECT_CHAT_WINDOW_SIZE.height}px`');
  max-width: calc(100vw - 16px);
  max-height: calc(100vh - 16px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  background: var(--el-bg-color);
  box-shadow: 0 12px 32px rgb(15 23 42 / 16%);
  pointer-events: auto;
}

.project-chat-window__header {
  display: flex;
  min-height: 52px;
  padding: 8px 8px 8px 14px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
  cursor: grab;
  user-select: none;
}

.project-chat-window__header--dragging {
  cursor: grabbing;
}

.project-chat-window__heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  cursor: text;
  user-select: text;
}

.project-chat-window__title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.project-chat-window__heading strong,
.project-chat-window__subtitle {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-chat-window__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.project-chat-window__actions {
  display: flex;
  flex: none;
  align-items: center;
}

.project-chat-window__actions .el-button + .el-button {
  margin-left: 2px;
}

.project-chat-window__body {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.project-chat-dock__taskbar {
  position: fixed;
  right: 16px;
  bottom: 16px;
  display: flex;
  max-width: calc(100vw - 32px);
  justify-content: flex-end;
  gap: 8px;
  pointer-events: auto;
}

.project-chat-dock__chat-tasks {
  display: flex;
  min-width: 0;
  gap: 8px;
  overflow-x: auto;
}

.project-chat-task,
:slotted(.floating-dock-task) {
  display: inline-flex;
  flex-shrink: 0;
  max-width: 280px;
  height: 38px;
  padding: 0 14px;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 19px;
  color: var(--el-color-primary-dark-2);
  background: var(--el-bg-color);
  box-shadow: var(--el-box-shadow-light);
  cursor: pointer;
}

.project-chat-task span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-chat-task__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.project-chat-task__unread {
  flex: none;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  color: #fff;
  background: var(--el-color-danger);
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

.project-chat-window--solo {
  inset: 8px;
  width: auto;
  height: auto;
  max-width: none;
  max-height: none;
}

.project-chat-window--solo .project-chat-window__header {
  cursor: default;
}
</style>
