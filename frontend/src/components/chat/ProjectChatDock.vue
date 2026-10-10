<template>
  <Teleport to="body">
    <div v-if="state.windows.length || hasExtraTasks || workspaceVisible || showWorkspaceTask" class="project-chat-dock" :class="{ 'project-chat-dock--immersive': workspaceVisible && state.workspaceMaximized }" aria-label="全局悬浮窗口">
      <div v-show="workspaceVisible" class="chat-workspace-shell" :class="{ 'chat-workspace-shell--maximized': state.workspaceMaximized }" :style="workspaceShellStyle" @mousedown="focusWorkspace">
        <ChatWorkspace
          :sessions="sessions"
          :active-key="state.activeKey"
          :error="followedError"
          :narrow="workspaceNarrow"
          :sidebar-open="sidebarOpen"
          :size-mode="state.workspaceSize"
          :maximized="state.workspaceMaximized"
          :session-width="workspaceNarrow ? 240 : sidebarWidth"
          :title="activeWindow?.title || '沟通'"
          :subtitle="activeWindow?.subtitle || ''"
          :project-id="activeWindow?.projectId || ''"
          :project-type="activeWindow?.projectType || ''"
          :meta-loading="!!activeWindow?.metaLoading"
          :dragging="draggingKey === '__workspace__'"
          @select="selectWorkspaceSession($event.key)"
          @open="openFollowed"
          @close="closeChat($event.key)"
          @close-active="activeWindow && closeChat(activeWindow.key)"
          @minimize="minimizeWorkspace"
          @cycle-size="cycleWorkspaceSize"
          @resize="setWorkspaceSize"
          @fullscreen="openFullscreen"
          @pin="pinChat()"
          @toggle-maximize="toggleWorkspaceMaximize"
          @toggle-layout="setLayout('float')"
          @open-search="openSearch(state.activeKey)"
          @toggle-sidebar="sidebarOpen = !sidebarOpen"
          @header-mousedown="startWorkspaceDrag"
          @header-dblclick="onWorkspaceDblClick"
          @retry="refreshFollowed"
          @preference="updatePreference"
        />
      </div>

      <section
        v-for="chatWindow in state.windows"
        v-show="isChatWindowVisible(chatWindow) && !(state.layout === 'workspace' && workspaceNarrow && sidebarOpen)"
        :key="chatWindow.key"
        class="project-chat-window"
        :class="windowClass(chatWindow)"
        :style="windowStyle(chatWindow)"
        @mousedown="onWindowMouseDown(chatWindow)"
      >
        <header
          v-show="state.layout !== 'workspace'"
          class="project-chat-window__header"
          :class="{ 'project-chat-window__header--dragging': draggingKey === chatWindow.key }"
          @mousedown="startDrag($event, chatWindow)"
          @dblclick="onHeaderDblClick($event, chatWindow)"
        >
          <div class="project-chat-window__heading">
            <div class="project-chat-window__title-row">
              <strong :title="chatWindow.title">{{ chatWindow.title }}</strong>
              <el-tag size="small" effect="plain" :type="chatWindow.projectType === 'annotation' ? 'success' : 'primary'">
                {{ chatWindow.projectType === 'direct' ? '单聊' : chatWindow.projectType === 'annotation' ? '标注' : '笔译' }}
              </el-tag>
            </div>
            <div class="project-chat-window__subtitle-row">
              <span v-if="chatWindow.metaLoading" class="project-chat-window__subtitle">正在加载项目信息…</span>
              <span v-else-if="chatWindow.subtitle" class="project-chat-window__subtitle" :title="chatWindow.subtitle">
                {{ chatWindow.subtitle }}
              </span>
              <ChatProjectActions :project-id="chatWindow.projectId" :project-type="chatWindow.projectType" />
            </div>
          </div>
          <div class="project-chat-window__actions">
            <el-button link aria-label="聊天记录" title="聊天记录" @click="openSearch(chatWindow.key)">
              <el-icon><Search /></el-icon>
            </el-button>
            <ChatWindowStateMenu v-if="!isCompactScreen" :size-mode="chatWindow.sizeMode" :pinned="state.pinnedKey === chatWindow.key" @resize="setSize(chatWindow.key, $event)" @workspace="setLayout('workspace')" @fullscreen="maximizeChat(chatWindow.key)" @pin="pinChat(chatWindow.key)" />
            <el-button link aria-label="最小化项目沟通" title="最小化" @click="minimizeChat(chatWindow.key)">
              <el-icon><Minus /></el-icon>
            </el-button>
            <el-button link aria-label="关闭项目沟通" title="关闭" @click="closeChat(chatWindow.key)">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </header>
        <div class="project-chat-window__body">
          <component
            :is="chatWindow.projectType === 'direct' ? DirectChat : chatWindow.projectType === 'annotation' ? AnnotationGroupChat : ProjectChatPanel"
            :ref="(el) => setPanelRef(chatWindow.key, el)"
            :project-id="chatWindow.projectId"
            :target-message-id="chatWindow.targetMessageId"
            :project-type="chatWindow.projectType"
            :active="isChatWindowVisible(chatWindow)"
            :history-placement="historyPlacement(chatWindow)"
            conversation-mode
            compact
            :text-only="chatWindow.projectType === 'annotation'"
            :always-enabled="chatWindow.projectType === 'annotation'"
            @unread="incrementUnread(chatWindow.key)"
          />
        </div>
      </section>

      <div v-if="minimizedWindows.length || showWorkspaceTask || hasExtraTasks" class="project-chat-dock__taskbar">
        <div v-if="minimizedWindows.length || showWorkspaceTask" class="project-chat-dock__chat-tasks">
          <button
            v-if="showWorkspaceTask"
            type="button"
            class="project-chat-task"
            title="恢复沟通"
            @click="restoreWorkspace"
          >
            <el-icon><ChatDotRound /></el-icon>
            <span>沟通</span><span v-if="mentionTotal" class="project-chat-task__unread">@</span>
            <span v-if="workspaceUnread" class="project-chat-task__unread">
              {{ workspaceUnread > 99 ? '99+' : workspaceUnread }}
            </span>
          </button>
          <button
            v-for="chatWindow in minimizedWindows"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound, Close, Minus, Search } from '@element-plus/icons-vue'
import ProjectChatPanel from '@/components/ProjectChatPanel.vue'
import { chatRequest } from '@/api/projectChat'
import { ElMessage } from 'element-plus'
import DirectChat from './DirectChat.vue'
import ChatProjectActions from './ChatProjectActions.vue'
import AnnotationGroupChat from '@/components/chat/AnnotationGroupChat.vue'
import ChatWorkspace from '@/components/chat/ChatWorkspace.vue'
import ChatWindowStateMenu from '@/components/chat/ChatWindowStateMenu.vue'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import {
  isChatWindowVisible,
  resolveChatSize,
  useProjectChatDock,
} from '@/composables/useProjectChatDock'

defineProps({ hasExtraTasks: { type: Boolean, default: false } })

const {
  state,
  openChat,
  closeChat,
  closeAllChats,
  minimizeChat,
  restoreChat,
  focusChat,
  focusWorkspace,
  setPosition,
  setWorkspacePosition,
  clampAllPositions,
  incrementUnread,
  setSize,
  setWorkspaceSize,
  pinChat,
  openFullscreen,
  toggleQuickSize,
  cycleWorkspaceSize,
  toggleWorkspaceMaximize,
  setLayout,
  selectSession,
  minimizeWorkspace,
  restoreWorkspace,
  ensurePreferences,
} = useProjectChatDock()
const { sessions: followed, mentionTotal, error: followedError, refresh: refreshFollowed } = useAnnotationFollowed()

const COMPACT_SCREEN_WIDTH = 768
const WORKSPACE_HEADER = 52
const isCompactScreen = ref(false)
const draggingKey = ref('')
const sidebarOpen = ref(true)
const panelRefs = new Map()

const setPanelRef = (key, el) => {
  if (el) panelRefs.set(key, el)
  else panelRefs.delete(key)
}

const workspaceNarrow = computed(() => resolveChatSize(state.workspaceMaximized ? 'maximized' : state.workspaceSize).width < 640)
const workspaceVisible = computed(() => (
  state.layout === 'workspace'
  && !state.workspaceMinimized
  && (state.workspaceOpened || state.windows.length > 0)
))
const showWorkspaceTask = computed(() => (
  state.layout === 'workspace'
  && state.workspaceMinimized
  && (state.workspaceOpened || state.windows.length > 0)
))
const minimizedWindows = computed(() => (
  state.layout !== 'workspace'
    ? state.windows.filter(item => item.minimized && (!state.pinnedKey || state.pinnedKey === item.key))
    : []
))
const sidebarWidth = computed(() => {
  if (!workspaceVisible.value) return 0
  if (workspaceNarrow.value) return 0
  return state.workspaceMaximized ? 280 : 240
})
const activeWindow = computed(() => state.windows.find(item => item.key === state.activeKey) || null)
const sessions = computed(() => {
  const rows = followed.value.map(s => ({ ...s, projectType: s.kind, opened: state.windows.some(w => w.key === s.key) }))
  for (const item of state.windows) {
    if (!rows.some(s => s.key === item.key)) rows.push({ ...item, opened: true })
  }
  return rows
})
async function updatePreference({ session, data }) {
  try { await chatRequest(`sessions/${session.projectType}/${session.projectId}/preferences`, { method: 'put', data }); await refreshFollowed() }
  catch (e) { ElMessage.error(e.detail || e.message || '更新会话偏好失败') }
}
function updateTitle() {
  const cleanTitle = document.title.replace(/^\[有人@我\]\s*/, '')
  document.title = mentionTotal.value && !document.hasFocus() ? `[有人@我] ${cleanTitle}` : cleanTitle
}
watch(mentionTotal, updateTitle)
const route = useRoute()
watch(() => route.fullPath, () => nextTick(updateTitle))
onMounted(() => { window.addEventListener('focus', updateTitle); window.addEventListener('blur', updateTitle) })
onBeforeUnmount(() => { window.removeEventListener('focus', updateTitle); window.removeEventListener('blur', updateTitle); document.title = document.title.replace(/^\[有人@我\]\s*/, '') })
const workspaceUnread = computed(() => sessions.value.reduce((sum, item) => sum + (Number(item.unread) || 0), 0))
const workspaceFrameMode = computed(() => (state.workspaceMaximized ? 'maximized' : state.workspaceSize))
const workspaceShellStyle = computed(() => {
  const size = resolveChatSize(workspaceFrameMode.value)
  return {
    left: `${state.workspaceX}px`,
    top: `${state.workspaceY}px`,
    width: `${size.width}px`,
    height: `${size.height}px`,
    zIndex: state.workspaceZ,
  }
})
const contentRect = computed(() => {
  const size = resolveChatSize(workspaceFrameMode.value)
  const side = sidebarWidth.value
  return {
    x: state.workspaceX + side,
    y: state.workspaceY + WORKSPACE_HEADER,
    width: Math.max(160, size.width - side),
    height: Math.max(160, size.height - WORKSPACE_HEADER),
  }
})

const historyPlacement = chatWindow => {
  const mode = state.layout === 'workspace' ? workspaceFrameMode.value : chatWindow.sizeMode
  return mode === 'large' || mode === 'maximized' ? 'side' : 'overlay'
}
const frameSize = chatWindow => {
  if (state.layout !== 'workspace') return chatWindow.sizeMode || 'small'
  return state.workspaceMaximized ? 'large' : state.workspaceSize
}
const windowClass = chatWindow => ({
  'project-chat-window--solo': isCompactScreen.value && state.layout !== 'workspace',
  'project-chat-window--embedded': state.layout === 'workspace',
  'project-chat-window--pinned': state.layout === 'float' && state.pinnedKey === chatWindow.key,
  'project-chat-window--immersive': state.workspaceMaximized && state.layout === 'workspace',
  [`project-chat-window--${frameSize(chatWindow)}`]: true,
})

const openSearch = (key) => {
  if (!key) return
  focusChat(key)
  panelRefs.get(key)?.openSearch?.()
}

const maximizeChat = (key) => {
  focusChat(key)
  openFullscreen()
}

const openFollowed = (session) => {
  openChat({
    projectId: session.projectId,
    projectType: session.projectType,
    title: session.title,
    subtitle: session.subtitle,
  })
  if (workspaceNarrow.value) sidebarOpen.value = false
}

const selectWorkspaceSession = (key) => {
  selectSession(key)
  if (workspaceNarrow.value) sidebarOpen.value = false
}

const windowStyle = (chatWindow) => {
  if (state.layout === 'workspace') {
    const rect = contentRect.value
    return {
      left: `${rect.x}px`,
      top: `${rect.y}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      zIndex: state.workspaceZ,
      borderRadius: state.workspaceMaximized ? '0' : (sidebarWidth.value ? '0 0 12px 0' : '0 0 12px 12px'),
    }
  }
  if (isCompactScreen.value) return { zIndex: chatWindow.zIndex }
  const size = resolveChatSize(chatWindow.sizeMode || 'small')
  return {
    left: `${chatWindow.x}px`,
    top: `${chatWindow.y}px`,
    width: `${size.width}px`,
    height: `${size.height}px`,
    zIndex: chatWindow.zIndex,
  }
}

const dragState = { key: '', offsetX: 0, offsetY: 0, moved: false }

const handleDragMove = (event) => {
  if (!dragState.key) return
  if (Math.abs(event.movementX) + Math.abs(event.movementY) > 0) dragState.moved = true
  if (dragState.key === '__workspace__') {
    setWorkspacePosition(event.clientX - dragState.offsetX, event.clientY - dragState.offsetY)
    return
  }
  setPosition(dragState.key, event.clientX - dragState.offsetX, event.clientY - dragState.offsetY)
}

const stopDrag = () => {
  dragState.key = ''
  draggingKey.value = ''
  window.removeEventListener('mousemove', handleDragMove)
  window.removeEventListener('mouseup', stopDrag)
}

const beginDrag = (event, key, originX, originY) => {
  event.preventDefault()
  dragState.key = key
  dragState.offsetX = event.clientX - originX
  dragState.offsetY = event.clientY - originY
  dragState.moved = false
  draggingKey.value = key
  window.addEventListener('mousemove', handleDragMove)
  window.addEventListener('mouseup', stopDrag)
}

// 仅标题栏空白区域作为拖拽手柄；项目名、订单号和按钮保留文字选择与点击。
const startDrag = (event, chatWindow) => {
  if (isCompactScreen.value || event.button !== 0) return
  if (event.target.closest('.project-chat-window__heading, .project-chat-window__actions, button, a')) return
  focusChat(chatWindow.key)
  beginDrag(event, chatWindow.key, chatWindow.x, chatWindow.y)
}

const startWorkspaceDrag = (event) => {
  if (isCompactScreen.value || state.workspaceMaximized || event.button !== 0) return
  if (event.target.closest('.chat-workspace__heading, .chat-workspace__actions, button, a, input')) return
  focusWorkspace()
  beginDrag(event, '__workspace__', state.workspaceX, state.workspaceY)
}

const onHeaderDblClick = (event, chatWindow) => {
  if (isCompactScreen.value || dragState.moved) return
  if (event.target.closest('.project-chat-window__heading, .project-chat-window__actions, button, a')) return
  toggleQuickSize(chatWindow.key)
}

const onWorkspaceDblClick = (event) => {
  if (dragState.moved) return
  if (event.target.closest('.chat-workspace__heading, .chat-workspace__actions, button, a, input')) return
  if (state.workspaceMaximized) toggleWorkspaceMaximize()
  else cycleWorkspaceSize()
}

const onWindowMouseDown = (chatWindow) => {
  if (state.layout === 'workspace') focusWorkspace()
  else focusChat(chatWindow.key)
}

// 小屏幕只保留最近使用的会话展开，其余自动最小化。工作区模式按当前会话显示，不改各窗口的最小化标记。
const enforceSoloWindow = () => {
  if (!isCompactScreen.value || state.layout === 'workspace') return
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

const onBusinessDialogOpened = (event) => {
  if (state.layout !== 'float' || !state.pinnedKey) return
  const overlay = event.detail?.element?.closest?.('.el-overlay')
  focusChat(state.pinnedKey, overlay ? Number(window.getComputedStyle(overlay).zIndex) : 0)
}

watch(() => state.windows.length, () => {
  enforceSoloWindow()
})
watch(workspaceNarrow, (narrow) => {
  if (narrow) sidebarOpen.value = false
}, { immediate: true })

onMounted(() => {
  ensurePreferences()
  syncViewportState()
  window.addEventListener('resize', syncViewportState)
  document.addEventListener('app-dialog-opened', onBusinessDialogOpened)
})

onBeforeUnmount(() => {
  stopDrag()
  window.removeEventListener('resize', syncViewportState)
  document.removeEventListener('app-dialog-opened', onBusinessDialogOpened)
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

.chat-workspace-shell {
  position: fixed;
  display: flex;
  overflow: hidden;
  border-radius: 12px;
  outline: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  box-shadow: 0 12px 32px rgb(15 23 42 / 16%);
  pointer-events: auto;
}

.chat-workspace-shell--maximized {
  border-radius: 0;
  outline: 0;
}

/* 持续的提及提醒也必须避开全屏标题栏，确保还原、最小化、关闭始终可点击。 */
:global(body:has(.project-chat-dock--immersive) .el-notification) {
  margin-top: 52px;
  max-height: calc(100vh - 88px);
  overflow-y: auto;
}

.project-chat-window--immersive :deep(.group-timeline),
.project-chat-window--immersive :deep(.chat-conversation) {
  padding: 24px 32px;
  background: var(--el-fill-color-light);
}

.project-chat-window--immersive :deep(.group-composer),
.project-chat-window--immersive :deep(.chat-composer--conversation) {
  padding: 12px 24px;
}

.project-chat-window--immersive :deep(.group-composer textarea) {
  min-height: 110px;
  box-shadow: none;
}

.project-chat-window {
  position: fixed;
  display: flex;
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

.project-chat-window--embedded {
  border: 0;
  box-shadow: none;
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

.project-chat-window__subtitle-row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.project-chat-window__subtitle-row .project-chat-window__subtitle,
.project-chat-window__title-row strong {
  min-width: 0;
}

.project-chat-window__title-row .el-tag {
  flex-shrink: 0;
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

.project-chat-window--medium :deep(.group-bubble),
.project-chat-window--medium :deep(.chat-conversation-item__main) {
  max-width: min(640px, 88%);
}

.project-chat-window--large :deep(.group-bubble),
.project-chat-window--large :deep(.chat-conversation-item__main) {
  max-width: min(760px, 78%);
}

.project-chat-window--medium :deep(.group-file .el-image) {
  max-width: 360px;
  max-height: 240px;
}

.project-chat-window--large :deep(.group-file .el-image) {
  max-width: 480px;
  max-height: 320px;
}

.project-chat-window--medium :deep(.message-attachment),
.project-chat-window--medium :deep(.message-attachment img) {
  width: 180px;
  height: 128px;
}

.project-chat-window--large :deep(.message-attachment),
.project-chat-window--large :deep(.message-attachment img) {
  width: 240px;
  height: 160px;
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
  width: auto !important;
  height: auto !important;
  max-width: none;
  max-height: none;
}

.project-chat-window--solo .project-chat-window__header {
  cursor: default;
}
</style>
