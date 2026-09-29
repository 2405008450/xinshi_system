<template>
  <div class="chat-workspace__frame">
    <header
      class="chat-workspace__header"
      :class="{ 'chat-workspace__header--dragging': dragging }"
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
        <el-button link aria-label="独立窗口" title="切换到独立窗口" @click="emit('toggle-layout')">
          <el-icon><CopyDocument /></el-icon>
        </el-button>
        <el-button link aria-label="窗口尺寸" :title="`窗口尺寸：${sizeLabel}，点击切换`" @click="emit('cycle-size')">{{ sizeLabel }}</el-button>
        <el-button link aria-label="最小化沟通" title="最小化" @click="emit('minimize')">
          <el-icon><Minus /></el-icon>
        </el-button>
        <el-button v-if="activeKey" link aria-label="关闭当前会话" title="关闭当前会话" @click="emit('close-active')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </header>
    <div class="chat-workspace__body">
      <aside v-show="!narrow || sidebarOpen" class="chat-workspace__sessions" :style="{ width: sidebarOpen || !narrow ? '240px' : '0' }">
        <div class="chat-workspace__session-tools">
          <div class="chat-workspace__tabs" role="tablist">
            <button type="button" :class="{ 'is-active': tab === 'all' }" @click="tab = 'all'">消息</button>
            <button type="button" :class="{ 'is-active': tab === 'unread' }" @click="tab = 'unread'">未读</button>
          </div>
          <el-input v-model="keyword" clearable size="small" placeholder="搜索会话" @keyup.enter="applyKeyword" />
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
          >
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
import { computed, ref, watch } from 'vue'
import { Close, CopyDocument, Minus, Search } from '@element-plus/icons-vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  activeKey: { type: String, default: '' },
  error: { type: String, default: '' },
  narrow: { type: Boolean, default: false },
  sidebarOpen: { type: Boolean, default: true },
  sizeMode: { type: String, default: 'medium' },
  title: { type: String, default: '沟通' },
  subtitle: { type: String, default: '' },
  projectType: { type: String, default: '' },
  metaLoading: { type: Boolean, default: false },
  dragging: { type: Boolean, default: false },
})
const emit = defineEmits([
  'select', 'open', 'close', 'close-active', 'minimize', 'cycle-size', 'toggle-layout',
  'open-search', 'toggle-sidebar', 'header-mousedown', 'header-dblclick', 'retry',
])

const tab = ref('all')
const keyword = ref('')
const appliedKeyword = ref('')
let keywordTimer = 0
const sizeLabel = computed(() => (props.sizeMode === 'large' ? '大' : '中'))

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
</script>

<style scoped>
.chat-workspace__frame {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  flex-direction: column;
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
