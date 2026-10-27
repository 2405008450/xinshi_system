<template>
  <Teleport to="body">
    <div v-if="state.windows.length || hasExtraTasks || workspaceVisible || showWorkspaceTask" class="project-chat-dock" :class="{ 'project-chat-dock--immersive': workspaceVisible && state.workspaceMaximized }" aria-label="全局悬浮窗口">
      <div v-show="workspaceVisible" class="chat-workspace-shell" :class="{ 'chat-workspace-shell--maximized': state.workspaceMaximized, 'chat-workspace-shell--mobile': workspaceMobile }" :style="workspaceShellStyle" @mousedown="focusWorkspace">
        <WindowFrameHandles ref="workspaceFrame" :disabled="state.workspaceMaximized || workspaceMobile" @change="resizeWorkspaceRect" />
        <ChatWorkspace
          :active="workspaceVisible"
          :mobile="workspaceMobile"
          :wide-header="contentRect.wideHeader"
          :sessions="sessions"
          :search-sessions="followed.map(row => ({...row,projectType:row.kind}))"
          :recent-closed="state.recentClosedSessions.filter(item => followed.some(row => (item.sessionKeys || [item.key]).includes(row.key)))"
          @restore-closed="restoreClosedSession"
          @pane-change="workspacePane = $event"
          @context-empty="state.activeKey = ''"
          :mention-history-total="mentionHistoryTotal"
          :project-mentions="mentionPreview"
          @browse-project-mentions="previewProject = $event"
          @select-project-mention="selectPreviewMention"
          @more-project-mentions="mentionPreview.loadMore"
          @retry-project-mentions="mentionPreview.refresh"
          :active-key="activeWindow?.conversationKey || state.activeKey"
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
          @locate-mention="locateMention"
          @close="closeSessionGroup"
          @close-active="closeActiveSession"
          @exit-workspace="closeAllChats"
          @project-navigate="minimizeWorkspace"
          @open-multiple="multiPicker.open(state.tileMode || 'small')"
          @duplicate-window="duplicateChat(state.activeKey)"
          @minimize="minimizeWorkspace"
          @cycle-size="cycleWorkspaceSize"
          @resize="setWorkspaceSize"
          @fullscreen="openFullscreen"
          @pin="pinChat()"
          @toggle-maximize="toggleWorkspaceMaximize"
          @normal-size="normalWorkspace"
          @toggle-layout="setLayout('float')"
          @open-search="openSearch(state.activeKey)"
          @toggle-sidebar="sidebarOpen = !sidebarOpen"
          @header-mousedown="startWorkspaceDrag"
          @header-dblclick="onWorkspaceDblClick"
          @retry="refreshFollowed"
          @preference="updatePreference"
          @categories-changed="categoriesChanged"
          @contact-opened="onContactOpened"
        />
      </div>

      <div v-if="tiled" class="chat-tile-toolbar">
        <strong>{{ state.tileMode === 'medium' ? '中窗' : '小窗' }}平铺 · {{ tileWindows.length }}/{{ state.tileMode === 'medium' ? 3 : 6 }}</strong>
        <el-button size="small" @click="multiPicker.open(state.tileMode)">选择会话</el-button>
        <el-button size="small" @click="multiPicker.open(state.tileMode === 'small' ? 'medium' : 'small')">切换{{ state.tileMode === 'small' ? '中窗' : '小窗' }}</el-button>
        <span>Tab 下一输入框 · Shift+Tab 上一输入框</span>
        <el-button size="small" title="退出整个会话窗口，保留聊天记录" @click="closeAllChats">退出会话窗口</el-button>
        <el-button size="small" @click="exitTiling">退出多窗状态</el-button>
      </div>
      <div :class="{ 'chat-tile-grid': tiled }" :style="tiled ? tileGridStyle : undefined" @keydown.capture="cycleComposer">
      <section
        v-for="chatWindow in state.windows"
        v-show="chatWindow.accessConfirmed !== false && isChatWindowVisible(chatWindow) && !(state.layout === 'workspace' && (['topics','summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(workspacePane) || (workspaceNarrow && sidebarOpen)))"
        :key="chatWindow.key"
        :data-chat-key="chatWindow.key"
        class="project-chat-window"
        :class="windowClass(chatWindow)"
        :style="windowStyle(chatWindow)"
        @mousedown="onWindowMouseDown(chatWindow)"
      >
        <WindowFrameHandles v-if="state.layout!=='workspace'" :ref="el=>el?windowFrames.set(chatWindow.key,el):windowFrames.delete(chatWindow.key)" @change="rect=>resizeChatRect(chatWindow,rect)" />
        <header
          v-show="state.layout !== 'workspace'"
          class="project-chat-window__header"
          :class="{ 'project-chat-window__header--dragging': draggingKey === chatWindow.key }"
          @mousedown="startDrag($event, chatWindow)"
          @dblclick="onHeaderDblClick($event, chatWindow)"
        >
          <div class="project-chat-window__heading">
            <ChatOrderIdentity v-if="['annotation', 'translation'].includes(chatWindow.projectType)" :title="chatWindow.title" :order-no="chatWindow.subtitle" :project-type="chatWindow.projectType" :project-id="chatWindow.projectId" show-managers />
            <div v-else class="project-chat-window__title-row">
              <strong :title="chatWindow.title">{{ chatWindow.title }}</strong>
              <el-tag size="small" effect="plain" :type="chatWindow.projectType === 'annotation' ? 'success' : 'primary'">
                {{ chatWindow.projectType === 'discussion' ? '讨论' : chatWindow.projectType === 'direct' ? '单聊' : chatWindow.projectType === 'annotation' ? '标注' : '笔译' }}
              </el-tag>
            </div>
            <div class="project-chat-window__subtitle-row" :title="chatWindow.subtitle">
              <span v-if="chatWindow.metaLoading" class="project-chat-window__subtitle">正在加载项目信息…</span>
              <span v-else-if="chatWindow.subtitle" class="project-chat-window__subtitle" :title="chatWindow.subtitle">
                {{ chatWindow.subtitle }}
              </span>

            </div>
          </div>
          <div class="chat-header-command-row" title="横向滚动查看更多操作" @mousedown.stop>

          <div class="project-chat-window__actions">
            <ChatTopicNavigation v-if="chatWindow.projectType !== 'discussion'" compact icon-only :project-id="chatWindow.projectId" :project-type="chatWindow.projectType" />
            <ChatConversationMore :project-id="chatWindow.projectId" :project-type="chatWindow.projectType" :can-duplicate="['annotation','translation'].includes(chatWindow.projectType)" @duplicate="duplicateChat(chatWindow.key)" @multiple="multiPicker.open(state.tileMode || 'small')">
            <div :id="`chat-tools-${chatWindow.key.replaceAll(':', '-')}`" class="chat-header-session-tools" />
            <ChatConversationParticipants menu-layout v-if="['translation', 'discussion'].includes(chatWindow.projectType)" :project-id="chatWindow.projectId" :project-type="chatWindow.projectType" />
            <AnnotationChatInbox menu-layout @navigate="minimizeChat(chatWindow.key)" />
            </ChatConversationMore>
            <span class="chat-header-divider" />
            <el-button v-if="!isCompactScreen" link aria-label="固定小窗" title="固定当前小窗，边聊边工作" @click="pinChat(chatWindow.key)"><el-icon><ChatPinIcon /></el-icon></el-button>

          </div>
          </div>
          <div class="chat-fixed-window-controls" @mousedown.stop @dblclick.stop><ChatProjectEntry :project-id="chatWindow.projectId" :project-type="chatWindow.projectType" @navigate="minimizeChat(chatWindow.key)" /><el-button link aria-label="聊天记录" title="聊天记录" @click="openSearch(chatWindow.key)"><el-icon><Search /></el-icon></el-button><button type="button" aria-label="最小化会话窗口" title="最小化" @click="minimizeChat(chatWindow.key)">−</button><button type="button" aria-label="最大化会话窗口" title="最大化" @click="maximizeChat(chatWindow.key)">□</button><button type="button" aria-label="退出整个会话窗口" title="退出整个会话窗口，保留聊天记录" @click.stop="closeAllChats">×</button></div>
        </header>
        <div class="project-chat-window__body">
          <div class="chat-conversation-close-row"><button type="button" aria-label="关闭当前会话" title="关闭当前会话，保留聊天记录" @click.stop="state.layout === 'workspace' ? closeWorkspaceSession() : closeChat(chatWindow.key)">×</button></div>
          <component
            :is="chatWindow.projectType === 'discussion' ? DiscussionConversation : chatWindow.projectType === 'direct' ? DirectChat : chatWindow.projectType === 'annotation' ? AnnotationGroupChat : ProjectChatPanel"
            :ref="(el) => setPanelRef(chatWindow.key, el)"
            :project-id="chatWindow.projectId"
            :target-message-id="chatWindow.targetMessageId"
            :project-type="chatWindow.projectType"
            :active="isChatWindowVisible(chatWindow) && !(state.layout === 'workspace' && ['topics','summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(workspacePane))"
            :history-placement="historyPlacement(chatWindow)"
            :toolbar-menu="true" :toolbar-target="state.layout === 'workspace' ? '#chat-workspace-session-tools' : `#chat-tools-${chatWindow.key.replaceAll(':', '-')}`"
            conversation-mode
            compact
            :text-only="chatWindow.projectType === 'annotation'"
            :always-enabled="chatWindow.projectType === 'annotation'"
            @unread="incrementUnread(chatWindow.key)"
          >
            <template v-if="chatWindow.projectType === 'annotation' && mentionSession(chatWindow).mentionHistoryCount" #mention-navigation>
              <ProjectMentionCorner :ref="el => setMentionRef(chatWindow.key, el)" :session="mentionSession(chatWindow)"
                :selected="state.activeKey === chatWindow.key" :locate="id => panelRefs.get(chatWindow.key)?.locate?.(id)"
                :cancel-locate="() => panelRefs.get(chatWindow.key)?.cancelLocate?.()" @activate="focusChat(chatWindow.key)" />
            </template>
          </component>
        </div>
      </section>
      </div>
      <ChatMultiWindowPicker ref="multiPicker" :sessions="sessions" />

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
            <span>沟通</span>
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
            <span v-if="chatWindow.mentionUnread" class="project-chat-task__unread">
              {{ chatWindow.mentionUnread > 99 ? '99+' : chatWindow.mentionUnread }}
            </span>
          </button>
        </div>
        <slot name="tasks" />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import ChatOrderIdentity from './ChatOrderIdentity.vue'
import ChatMultiWindowPicker from './ChatMultiWindowPicker.vue'
import { chatTileLayout } from '@/utils/chatTiling'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound, Search } from '@element-plus/icons-vue'
import ProjectChatPanel from '@/components/ProjectChatPanel.vue'
import { chatRequest } from '@/api/projectChat'
import { filterClosedSessions, mentionUnreadCount } from '@/utils/chatSessionList'
import { ElMessage } from 'element-plus'
import DirectChat from './DirectChat.vue'
import DiscussionConversation from './DiscussionConversation.vue'
import ChatConversationMore from './ChatConversationMore.vue'
import ChatPinIcon from './ChatPinIcon.vue'
import AnnotationGroupChat from '@/components/chat/AnnotationGroupChat.vue'
import ChatWorkspace from '@/components/chat/ChatWorkspace.vue'
import AnnotationChatInbox from './AnnotationChatInbox.vue'
import ChatProjectEntry from './ChatProjectEntry.vue'
import ChatConversationParticipants from './ChatConversationParticipants.vue'
import ProjectMentionCorner from './ProjectMentionCorner.vue'
import { useChatMentions } from '@/composables/useChatMentions'
import ChatTopicNavigation from './ChatTopicNavigation.vue'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { useChatNotifications } from '@/composables/useChatNotifications'
import WindowFrameHandles from '@/components/common/WindowFrameHandles.vue'
import {
  isChatWindowVisible,
  resolveChatSize,
  useProjectChatDock,
} from '@/composables/useProjectChatDock'

defineProps({ hasExtraTasks: { type: Boolean, default: false } })
useChatNotifications()

const {
  state,
  exitTiling,
  duplicateChat,
  openChat,
  closeChat,
  closeSessionEntry,
  restoreClosedSession,
  syncClosedSessionCatalog,
  closeWorkspaceSession,
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
const { sessions: followed, mentionTotal, mentionHistoryTotal, annotationMentionCounts, error: followedError, refresh: refreshFollowed } = useAnnotationFollowed()
watch(followed, syncClosedSessionCatalog, { immediate: true })

const COMPACT_SCREEN_WIDTH = 768
const workspaceRect=ref(null),chatRects=ref({})
const workspaceFrame=ref(),windowFrames=new Map()
function resizeWorkspaceRect(rect){focusWorkspace();workspaceRect.value=rect;state.workspaceX=rect.x;state.workspaceY=rect.y}
function resizeChatRect(chat,rect){if(tiled.value)state.tileMode='';focusChat(chat.key);chatRects.value[chat.key]=rect;chat.x=rect.x;chat.y=rect.y}
function normalWorkspace(){const active=state.activeKey;workspaceRect.value=null;if(state.workspaceMaximized)toggleWorkspaceMaximize();else setWorkspaceSize(state.workspaceSize);if(state.layout==='float'&&active)restoreChat(active)}
watch(()=>state.workspaceMaximized,()=>{workspaceRect.value=null})
watch(()=>state.workspaceSize,()=>{workspaceRect.value=null})
watch(()=>state.windows.map(row=>row.key),keys=>{for(const key of Object.keys(chatRects.value))if(!keys.includes(key))delete chatRects.value[key]})
const isCompactScreen = ref(false)
const viewportSize = ref({ width: window.innerWidth, height: window.innerHeight })
const multiPicker = ref(null)
const tiled = computed(() => state.layout === 'float' && !!state.tileMode)
const tileWindows = computed(() => state.windows.filter(item => !item.minimized && item.accessConfirmed !== false))
const tileGridStyle = computed(() => {
  const layout = chatTileLayout(tileWindows.value.length, state.tileMode, viewportSize.value.width, viewportSize.value.height)
  return { gridTemplateColumns: `repeat(${layout.columns}, minmax(0, 1fr))`, gridAutoRows: `${layout.rowHeight}px` }
})
function cycleComposer(event) {
  if (event.key !== 'Tab' || event.ctrlKey || event.altKey || event.metaKey || event.isComposing || state.layout !== 'float') return
  const selector = '.group-composer textarea, .chat-composer--conversation textarea, .discussion-chat__composer textarea, .chat-composer--conversation [contenteditable="true"]'
  const currentInput = event.target.matches(selector) ? event.target : event.target.closest?.(selector)
  if (!currentInput) return
  const root = event.currentTarget
  const inputs = [...root.querySelectorAll(selector)].filter(input => !input.disabled && input.getBoundingClientRect().width > 0 && input.closest('.project-chat-window')?.style.display !== 'none')
  if (inputs.length < 2) return
  event.preventDefault(); event.stopPropagation()
  const current = inputs.indexOf(currentInput), next = inputs[(current + (event.shiftKey ? -1 : 1) + inputs.length) % inputs.length]
  focusChat(next.closest('.project-chat-window').dataset.chatKey)
  next.focus({ preventScroll: true }); next.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}
const draggingKey = ref('')
const workspacePane = ref('messages')
const sidebarOpen = ref(true)
const panelRefs = new Map()
const mentionRefs = new Map()
const setMentionRef = (key, el) => { if (el) mentionRefs.set(key, el); else mentionRefs.delete(key) }
const previewProject = ref(null)
const previewQuery = useChatMentions(ref(''), computed(() => !!previewProject.value), computed(() => ({
  projectType: previewProject.value?.projectType, projectId: previewProject.value?.projectId,
})))
const mentionPreview = reactive({ project: previewProject, ...previewQuery })
const mentionSession = chatWindow => sessions.value.find(row => row.key === (chatWindow.conversationKey || chatWindow.key)) || chatWindow
async function selectPreviewMention(item) {
  const key = openChat({ projectId: item.projectId, projectType: item.projectType, title: item.title, subtitle: item.subtitle })
  if (workspaceNarrow.value) sidebarOpen.value = false
  await nextTick()
  if (state.activeKey === key) await mentionRefs.get(key)?.select(item)
}

const setPanelRef = (key, el) => {
  if (el) panelRefs.set(key, el)
  else panelRefs.delete(key)
}

const workspaceNarrow = computed(() => viewportSize.value.width < 640 || (!state.workspaceMaximized && workspaceRect.value?.width || resolveChatSize(state.workspaceMaximized ? 'maximized' : state.workspaceSize).width) < 640)
// 手机视口：会话窗口铺满屏幕，列表与会话分两级页面显示。
const workspaceMobile = computed(() => viewportSize.value.width < 640)
const MOBILE_CHAT_HEADER = 52
function closeActiveSession() {
  closeWorkspaceSession()
  if (workspaceMobile.value) sidebarOpen.value = true
}
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
  return state.workspaceMaximized ? 300 : 280
})
const activeWindow = computed(() => state.windows.find(item => item.key === state.activeKey && item.accessConfirmed !== false) || null)
const sessions = computed(() => {
  const rows = followed.value.map(s => ({ ...s, projectType: s.kind, opened: state.windows.some(w => (w.conversationKey || w.key) === s.key) }))
  for (const item of state.windows) {
    if (item.accessConfirmed === false) continue
    const conversationKey = item.conversationKey || item.key
    if (!rows.some(s => s.key === conversationKey)) rows.push({ ...item, key: conversationKey, opened: true })
  }
  const counts = new Map(annotationMentionCounts.value.map(item => [String(item.projectId), item.count]))
  // 先保持现有目录范围，再补充个人提及信息；历史提及不能把未关注项目带入目录。
  return filterClosedSessions(rows.map(row => ({ ...row, mentionHistoryCount: row.mentionHistoryCount ?? (row.projectType === 'annotation' ? counts.get(String(row.projectId)) || 0 : 0) })), state.closedSessionKeys)
})
function closeSessionGroup(session) {
  closeSessionEntry(session)
}
function onChatAccessGranted(event) {
  const key = `${event.detail.projectType}:${event.detail.projectId}`
  state.windows.filter(row => (row.conversationKey || row.key) === key).forEach(item => { item.accessConfirmed = true })
}
function onChatAccessDenied(event) {
  const key = `${event.detail.projectType}:${event.detail.projectId}`
  const matches = state.windows.filter(row => (row.conversationKey || row.key) === key)
  for (const item of matches) closeChat(item.key, { recordRecent: false })
  state.recentClosedSessions = state.recentClosedSessions.filter(item => !(item.sessionKeys || [item.key]).includes(key))
  refreshFollowed()
}
onMounted(() => {
  window.addEventListener('chat-conversation-access-granted', onChatAccessGranted)
  window.addEventListener('chat-conversation-access-denied', onChatAccessDenied)
})
onBeforeUnmount(() => {
  window.removeEventListener('chat-conversation-access-granted', onChatAccessGranted)
  window.removeEventListener('chat-conversation-access-denied', onChatAccessDenied)
})
async function updatePreference({ session, data }) {
  try { await chatRequest(session.projectType === 'discussion' ? `discussions/${session.projectId}/preferences` : `sessions/${session.projectType}/${session.projectId}/preferences`, { method: 'put', data }); await refreshFollowed() }
  catch (e) { ElMessage.error(e.detail || e.message || '更新会话偏好失败') }
}
function categoriesChanged(change) {
  if (change?.key) {
    const opened = state.windows.find(row => row.key === change.key)
    if (opened) opened.categoryIds = change.categoryIds
  }
  refreshFollowed()
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
const workspaceUnread = computed(() => mentionUnreadCount(sessions.value))
const workspaceFrameMode = computed(() => (state.workspaceMaximized ? 'maximized' : state.workspaceSize))
const workspaceShellStyle = computed(() => {
  // 视口变化也须使尺寸计算失效，不能只依赖窗口档位。
  void viewportSize.value
  if (workspaceMobile.value) return { left: '0', top: '0', width: '100vw', height: '100dvh', zIndex: state.workspaceZ }
  const size = !state.workspaceMaximized && workspaceRect.value || resolveChatSize(workspaceFrameMode.value)
  return {
    left: `${state.workspaceX}px`,
    top: `${state.workspaceY}px`,
    width: `${size.width}px`,
    height: `${size.height}px`,
    zIndex: state.workspaceZ,
  }
})
const contentRect = computed(() => {
  void viewportSize.value
  const size = !state.workspaceMaximized && workspaceRect.value || resolveChatSize(workspaceFrameMode.value)
  const side = sidebarWidth.value + (state.workspaceMaximized && !workspaceNarrow.value ? 56 : 0)
  const width = Math.max(160, size.width - side)
  const wideHeader = width >= 840
  const headerHeight = wideHeader ? 100 : 150
  return {
    x: state.workspaceX + side,
    y: state.workspaceY + headerHeight,
    width,
    height: Math.max(160, size.height - headerHeight),
    wideHeader,
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
  'project-chat-window--solo': !tiled.value && isCompactScreen.value && state.layout !== 'workspace',
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
    projectStatus: session.projectStatus,
  })
  if (workspaceNarrow.value) sidebarOpen.value = false
}

const selectWorkspaceSession = (key) => {
  selectSession(key)
  if (workspaceNarrow.value) sidebarOpen.value = false
}

const locateMention = async (item) => {
  const existing = state.windows.find(row => row.key === item.key)
  const repeated = existing?.targetMessageId === item.messageId
  const key = openChat({ projectId: item.projectId, projectType: item.projectType,
    title: item.title, subtitle: item.subtitle, messageId: item.messageId })
  if (workspaceNarrow.value) sidebarOpen.value = false
  // 再次点击同一条提及时，属性值未变化，仍需重新定位并高亮。
  if (repeated) { await nextTick(); await panelRefs.get(key)?.locate?.(item.messageId) }
}

const onContactOpened = () => {
  if (workspaceNarrow.value) sidebarOpen.value = false
}

const windowStyle = (chatWindow) => {
  if (tiled.value) return { position: 'relative', left: 'auto', top: 'auto', width: '100%', height: '100%', maxWidth: 'none', maxHeight: 'none', minWidth: '0', zIndex: 1 }
  if (state.layout === 'workspace') {
    if (workspaceMobile.value) {
      return { left: '0', top: `${MOBILE_CHAT_HEADER}px`, width: '100vw', height: `calc(100dvh - ${MOBILE_CHAT_HEADER}px)`, maxWidth: 'none', maxHeight: 'none', zIndex: state.workspaceZ, borderRadius: '0' }
    }
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
  if(chatRects.value[chatWindow.key]){const r=chatRects.value[chatWindow.key];return {left:`${r.x}px`,top:`${r.y}px`,width:`${r.width}px`,height:`${r.height}px`,zIndex:chatWindow.zIndex,position:'fixed',maxWidth:'none',maxHeight:'none'}}
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
  if (tiled.value) return
  if (isCompactScreen.value || event.button !== 0) return
  if (event.target.closest('.project-chat-window__heading, .project-chat-window__actions, button, a')) return
  focusChat(chatWindow.key)
  windowFrames.get(chatWindow.key)?.start(event)
}

const startWorkspaceDrag = (event) => {
  if (isCompactScreen.value || state.workspaceMaximized || event.button !== 0) return
  if (event.target.closest('.chat-workspace__heading, .chat-workspace__actions, button, a, input')) return
  focusWorkspace()
  workspaceFrame.value?.start(event)
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
  if (tiled.value) return
  if (!isCompactScreen.value || state.layout === 'workspace') return
  const expanded = state.windows
    .filter(item => !item.minimized)
    .sort((left, right) => right.lastActiveOrder - left.lastActiveOrder)
  expanded.slice(1).forEach((item) => { item.minimized = true })
}

const syncViewportState = () => {
  viewportSize.value = { width: window.innerWidth, height: window.innerHeight }
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
  if (narrow) sidebarOpen.value = workspaceMobile.value && !state.activeKey
}, { immediate: true })
watch(workspaceVisible, (visible) => {
  if (visible && workspaceMobile.value) sidebarOpen.value = !state.activeKey
})
watch(() => state.activeKey, (key) => {
  if (!key && workspaceMobile.value) sidebarOpen.value = true
})

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
.project-chat-window__close-button{position:absolute;z-index:2;right:8px;top:8px;display:flex;align-items:center;justify-content:center;width:36px;height:36px;box-sizing:border-box;padding:0;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;color:#334155;font:26px/1 Arial,sans-serif;cursor:pointer;opacity:1;visibility:visible}.project-chat-window__close-button:hover{color:#dc2626;border-color:#fca5a5;background:#fef2f2}.project-chat-window__close-button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:2px}
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

.chat-workspace-shell--mobile {
  border-radius: 0;
  outline: 0;
  box-shadow: none;
}

/* 持续的提及提醒也必须避开全屏标题栏，确保还原、最小化、关闭始终可点击。 */
:global(body:has(.project-chat-dock--immersive) .el-notification) {
  margin-top: 52px;
  max-height: calc(100vh - 88px);
  overflow-y: auto;
}

.project-chat-window--immersive :deep(.group-timeline),
.project-chat-window--immersive :deep(.chat-conversation) {
  padding: 20px 28px;
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
.project-chat-window__header{position:relative;padding-right:52px}.project-chat-window__actions{min-width:0;flex-shrink:1;overflow-x:auto;scrollbar-width:none}.project-chat-window__actions::-webkit-scrollbar{display:none}
.project-chat-window__exit-button{flex:none;margin:0;font-size:11px;padding:6px 8px}
</style>

<style scoped>
.project-chat-window__header{height:52px;min-height:52px;box-sizing:border-box;padding:0 8px 0 12px;gap:6px;background:white}
.project-chat-window__heading{flex:1}.project-chat-window__subtitle-row{display:none}.project-chat-window__title-row strong{font-size:13px}.project-chat-window__title-row .el-tag{font-size:10px}
.project-chat-window__actions :deep(.el-button){margin:0;width:28px;height:28px;padding:4px}.chat-header-session-tools{display:flex;align-items:center;flex:none}.chat-header-divider{width:1px;height:20px;background:#e2e8f0;margin:0 5px}
.project-chat-window--immersive :deep(.chat-composer--conversation){margin:10px 24px 16px;padding:10px 12px}
@media(max-width:600px){.project-chat-window__title-row .el-tag{display:none}.project-chat-window__actions :deep(.el-button){width:25px}.project-chat-window__header{gap:4px;padding:0 5px}}
.project-chat-window__exit-button{flex:none;margin:0;font-size:11px;padding:6px 8px}
</style>

<style scoped>
.project-chat-window__header{height:112px;min-height:112px;flex-wrap:wrap;align-content:center;gap:5px 8px;padding-top:5px;padding-bottom:5px}
.project-chat-window__heading{flex:0 0 100%;height:64px;min-width:0;overflow:hidden}
.project-chat-window__actions{flex:1;justify-content:flex-end}
:global(body:has(.project-chat-dock--immersive) .el-notification){margin-top:112px}
</style>

<style scoped>
.chat-tile-toolbar{position:fixed;inset:0 0 auto 0;min-height:46px;box-sizing:border-box;padding:7px 10px;display:flex;align-items:center;gap:7px;flex-wrap:wrap;background:white;border-bottom:1px solid #cbd5e1;pointer-events:auto;z-index:3}
.chat-tile-toolbar strong{font-size:13px}.chat-tile-toolbar>span{font-size:11px;color:#64748b}.chat-tile-toolbar .el-button{margin:0}
.chat-tile-grid{position:fixed;inset:78px 0 0;display:grid;align-content:start;gap:10px;padding:10px;overflow:auto;box-sizing:border-box;pointer-events:auto;background:#e8edf4}
.chat-tile-grid .project-chat-window{box-sizing:border-box;box-shadow:0 2px 8px #0f172a12}
.chat-tile-grid .project-chat-window:focus-within{outline:2px solid #3b82f6;outline-offset:-2px}
.chat-tile-grid :deep(.group-composer textarea),.chat-tile-grid :deep(.chat-composer--conversation textarea){max-height:80px!important}
.chat-multi-entry{flex:none;margin:0!important;font-size:11px;padding:6px 8px}
@media(min-width:1000px){.chat-tile-grid{top:48px}}
</style>

<style scoped>.chat-tile-grid .project-chat-window__exit-button,.chat-tile-grid .chat-multi-entry{display:none}</style>

<style scoped>
.chat-tile-grid :deep(.rich-editor__toolbar){max-height:54px;overflow-y:auto}
.chat-tile-grid :deep(.rich-editor__content .tiptap){min-height:48px!important;max-height:80px;overflow-y:auto}
</style>

<style scoped src="./chatHeader.css" />

<style scoped>
.project-chat-window__body{position:relative;display:flex;flex-direction:column;min-height:0}
.project-chat-window__body>:deep(.annotation-group),.project-chat-window__body>:deep(.project-chat-panel),.project-chat-window__body>:deep(.project-chat),.project-chat-window__body>:deep(.discussion-chat){flex:1;min-height:0}
.chat-conversation-close-row{display:flex;justify-content:flex-end;flex:none;height:28px;background:#f1f5f9;padding-right:8px;z-index:2}
.chat-conversation-close-row button{width:30px;height:26px;line-height:24px;border:0;border-radius:4px;background:transparent;font-size:22px;color:#64748b;cursor:pointer}.chat-conversation-close-row button:hover{background:#fee2e2;color:#dc2626}
</style>
