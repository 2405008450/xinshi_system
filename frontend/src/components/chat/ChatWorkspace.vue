<template>
  <div class="chat-workspace__frame" :class="{ 'chat-workspace--maximized': maximized, 'chat-workspace--narrow': narrow }" :style="{ '--chat-session-width': `${narrow ? 0 : sessionWidth}px` }">
    <header
      class="chat-workspace__header"
      :class="{ 'chat-workspace__header--dragging': dragging, 'chat-workspace__header--pinned': maximized }"
      @mousedown="emit('header-mousedown', $event)"
      @dblclick="emit('header-dblclick', $event)"
    >
      <div class="chat-workspace__heading">
        <div class="chat-workspace__title-row">
          <strong :title="title">{{ title || '沟通' }}</strong>
          <el-tag v-if="projectType" size="small" effect="plain" :type="projectType === 'annotation' ? 'success' : 'primary'">
            {{ projectType === 'annotation' ? '标注' : '笔译' }}
          </el-tag>
        </div>
        <span v-if="metaLoading" class="chat-workspace__subtitle">正在加载项目信息…</span>
        <span v-else-if="subtitle" class="chat-workspace__subtitle" :title="subtitle">{{ subtitle }}</span>
      </div>
      <div class="chat-workspace__actions">
        <el-button v-if="narrow" link aria-label="会话列表" title="会话列表" @click="emit('toggle-sidebar')">会话</el-button>
        <el-button v-if="activeKey" link aria-label="聊天记录" title="聊天记录" @click="emit('open-search')">
          <el-icon><Search /></el-icon>
        </el-button>
        <el-button v-if="activeKey" size="small" aria-label="固定小窗" title="固定当前小窗，边聊边工作" @click="emit('pin')"><el-icon><Position /></el-icon>固定小窗</el-button>
        <ChatWindowStateMenu v-if="!narrow" :size-mode="sizeMode" :maximized="maximized" workspace :has-session="!!activeKey" @resize="emit('resize', $event)" @fullscreen="emit('fullscreen')" @pin="emit('pin')" />
        <el-button link :aria-label="maximized ? '还原窗口' : '最大化'" :title="maximized ? '退出全屏，恢复原窗口' : '全屏沟通'" @click="emit('toggle-maximize')">
          <span class="chat-max-icon" :class="{ 'chat-max-icon--restore': maximized }" aria-hidden="true" />
        </el-button>
        <el-button link aria-label="最小化沟通" title="最小化" @click="emit('minimize')">
          <el-icon><Minus /></el-icon>
        </el-button>
        <el-button link aria-label="关闭聊天大屏" title="关闭大屏，保留会话" @click="emit('minimize')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </header>
    <div class="chat-workspace__body">
      <aside v-show="!narrow || sidebarOpen" class="chat-workspace__sessions" :style="{ width: `${sessionWidth}px` }">
        <div class="chat-workspace__session-tools">
          <div v-if="maximized" class="chat-workspace__brand"><el-icon><ChatDotRound /></el-icon><strong>项目沟通</strong><span>{{ sessions.length }} 个会话</span></div>
          <div class="chat-workspace__search"><el-input v-model="keyword" clearable size="small" placeholder="搜索项目名称、订单号" :prefix-icon="Search" @keyup.enter="applyKeyword" /><el-button size="small" @click="applyKeyword">查询</el-button></div>
          <div class="chat-workspace__tabs" role="tablist">
            <button type="button" :class="{ 'is-active': tab === 'all' }" @click="tab = 'all'">消息</button>
            <button type="button" :class="{ 'is-active': tab === 'unread' }" @click="tab = 'unread'">未读</button>
          </div>
        </div>
        <p v-if="error" class="chat-workspace__error" role="alert">{{ error }} <el-button link @click="emit('retry')">重试</el-button></p>
        <div class="chat-workspace__list">
          <el-empty v-if="!visibleSessions.length" :description="tab === 'unread' ? '没有未读消息' : '暂无会话'" :image-size="48" />
          <div
            v-for="session in visibleSessions"
            :key="session.key"
            class="chat-workspace__session"
            :class="{ 'is-active': session.opened && session.key === activeKey }"
            role="button"
            tabindex="0"
            @click="emit(session.opened ? 'select' : 'open', session)"
            @keydown.enter="emit(session.opened ? 'select' : 'open', session)"
            @keydown.space.prevent="emit(session.opened ? 'select' : 'open', session)"
          >
            <span v-if="maximized" class="chat-workspace__avatar" :class="{ 'chat-workspace__avatar--annotation': session.projectType === 'annotation' }" aria-hidden="true">{{ (session.title || '项目').slice(0, 1) }}</span>
            <span class="chat-workspace__session-main">
              <span class="chat-workspace__session-title">
                <strong :title="session.title">{{ session.title || '未命名项目' }}</strong>
                <el-tag size="small" effect="plain" :type="session.projectType === 'annotation' ? 'success' : 'primary'">
                  {{ session.projectType === 'annotation' ? '标注' : '笔译' }}
                </el-tag>
              </span>
              <small v-if="session.subtitle">{{ session.subtitle }}</small>
            </span>
            <el-badge :value="session.unread" :max="99" :hidden="!session.unread" />
            <span
              v-if="session.opened"
              class="chat-workspace__session-close"
              role="button"
              tabindex="0"
              aria-label="关闭会话"
              title="关闭"
              @click.stop="emit('close', session)"
              @keydown.enter.stop="emit('close', session)"
            >
              <el-icon><Close /></el-icon>
            </span>
          </div>
        </div>
      </aside>
      <div class="chat-workspace__stage">
        <div v-if="!activeKey" class="chat-workspace__empty">从左侧选择一个会话</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ChatDotRound, Close, Minus, Position, Search } from '@element-plus/icons-vue'
import ChatWindowStateMenu from './ChatWindowStateMenu.vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  activeKey: { type: String, default: '' },
  error: { type: String, default: '' },
  narrow: { type: Boolean, default: false },
  sidebarOpen: { type: Boolean, default: true },
  sizeMode: { type: String, default: 'medium' },
  maximized: { type: Boolean, default: false },
  sessionWidth: { type: Number, default: 240 },
  title: { type: String, default: '沟通' },
  subtitle: { type: String, default: '' },
  projectType: { type: String, default: '' },
  metaLoading: { type: Boolean, default: false },
  dragging: { type: Boolean, default: false },
})
const emit = defineEmits([
  'select', 'open', 'close', 'close-active', 'minimize', 'cycle-size', 'toggle-maximize', 'toggle-layout',
  'open-search', 'toggle-sidebar', 'header-mousedown', 'header-dblclick', 'retry', 'pin', 'resize', 'fullscreen',
])

const tab = ref('all')
const keyword = ref('')
const appliedKeyword = ref('')
let keywordTimer = 0

const applyKeyword = () => {
  window.clearTimeout(keywordTimer)
  appliedKeyword.value = keyword.value.trim().toLowerCase()
}

watch(keyword, (value) => {
  window.clearTimeout(keywordTimer)
  if (!value) {
    appliedKeyword.value = ''
    return
  }
  keywordTimer = window.setTimeout(applyKeyword, 400)
})

const visibleSessions = computed(() => props.sessions.filter((session) => {
  if (tab.value === 'unread' && !session.unread) return false
  if (!appliedKeyword.value) return true
  return `${session.title || ''} ${session.subtitle || ''}`.toLowerCase().includes(appliedKeyword.value)
}))
onBeforeUnmount(() => window.clearTimeout(keywordTimer))
</script>

<style scoped>
.chat-workspace__frame {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  flex-direction: column;
}

.chat-workspace--narrow .chat-workspace__sessions {
  position: absolute;
  z-index: 1;
  top: 52px;
  bottom: 0;
  left: 0;
  box-shadow: var(--el-box-shadow-light);
}

.chat-workspace--narrow .chat-workspace__heading {
  display: none;
}

.chat-workspace--narrow .chat-workspace__actions {
  width: 100%;
  justify-content: space-between;
}

.chat-workspace__header {
  display: flex;
  height: 52px;
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

.chat-workspace__header--dragging {
  cursor: grabbing;
}

.chat-workspace__header--pinned,
.chat-workspace__header--pinned.chat-workspace__header--dragging {
  cursor: default;
}

.chat-max-icon {
  display: inline-block;
  width: 12px;
  height: 12px;
  box-sizing: border-box;
  border: 1.5px solid currentColor;
  border-radius: 1px;
}

.chat-max-icon--restore {
  position: relative;
  border-color: transparent;
}

.chat-max-icon--restore::before,
.chat-max-icon--restore::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 8px;
  box-sizing: border-box;
  border: 1.5px solid currentColor;
  background: var(--el-fill-color-light);
}

.chat-max-icon--restore::before {
  left: 0;
  bottom: 0;
}

.chat-max-icon--restore::after {
  top: 0;
  right: 0;
}

.chat-workspace__heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  cursor: text;
  user-select: text;
}

.chat-workspace__title-row,
.chat-workspace__session-title,
.chat-workspace__actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-workspace__heading strong,
.chat-workspace__subtitle,
.chat-workspace__session-title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-workspace__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-workspace__actions {
  flex: none;
}

.chat-workspace__actions .el-button + .el-button {
  margin-left: 2px;
}

.chat-workspace__body {
  display: flex;
  min-height: 0;
  flex: 1;
}

.chat-workspace__sessions {
  display: flex;
  min-width: 0;
  flex: none;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
}

.chat-workspace__session-tools {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}

.chat-workspace__tabs {
  display: flex;
  gap: 4px;
}

.chat-workspace__tabs button {
  flex: 1;
  padding: 4px 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  font: inherit;
}

.chat-workspace__tabs button.is-active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.chat-workspace__list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.chat-workspace__session {
  display: flex;
  width: 100%;
  padding: 8px 10px;
  align-items: center;
  gap: 8px;
  border: 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.chat-workspace__session.is-active,
.chat-workspace__session:hover {
  background: var(--el-fill-color-light);
}

.chat-workspace--maximized .chat-workspace__sessions {
  background: var(--el-fill-color-lighter);
  grid-column: 1;
  grid-row: 1 / 3;
}

.chat-workspace--maximized {
  display: grid;
  grid-template-columns: var(--chat-session-width) minmax(0, 1fr);
  grid-template-rows: 52px minmax(0, 1fr);
}

.chat-workspace--maximized .chat-workspace__body {
  display: contents;
}

.chat-workspace--maximized .chat-workspace__header {
  grid-column: 2;
  grid-row: 1;
  box-sizing: border-box;
  background: var(--el-bg-color);
}

.chat-workspace--maximized .chat-workspace__stage {
  grid-column: 2;
  grid-row: 2;
  background: var(--el-fill-color-light);
}

.chat-workspace__brand,
.chat-workspace__search {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-workspace__brand {
  height: 36px;
  color: var(--el-text-color-primary);
}

.chat-workspace__brand > span {
  margin-left: auto;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-workspace__avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  font-size: 18px;
}

.chat-workspace__avatar--annotation {
  background: var(--el-color-success-light-8);
  color: var(--el-color-success-dark-2);
}

.chat-workspace--maximized .chat-workspace__session {
  min-height: 76px;
  box-sizing: border-box;
  padding: 14px;
}

.chat-workspace__session:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}

.chat-workspace--maximized .chat-workspace__session.is-active {
  background: var(--el-bg-color);
  box-shadow: inset 3px 0 0 var(--el-color-primary);
}

.chat-workspace--maximized .chat-workspace__list {
  padding: 4px 0 8px;
}

.chat-workspace__session-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.chat-workspace__session-main small {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-workspace__session-close {
  display: none;
  flex: none;
  color: var(--el-text-color-secondary);
}

.chat-workspace__session:hover .chat-workspace__session-close,
.chat-workspace__session:focus-within .chat-workspace__session-close {
  display: inline-flex;
}

.chat-workspace__stage {
  min-width: 0;
  flex: 1;
}

.chat-workspace__empty,
.chat-workspace__error {
  padding: 24px 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
}

.chat-workspace__error {
  color: var(--el-color-danger);
  text-align: left;
}
</style>
