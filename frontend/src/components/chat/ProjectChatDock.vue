<template>
  <Teleport to="body">
    <div v-if="state.windows.length" class="project-chat-dock" aria-label="项目沟通窗口">
      <div class="project-chat-dock__windows">
        <section
          v-for="chatWindow in state.windows"
          v-show="!chatWindow.minimized"
          :key="chatWindow.key"
          class="project-chat-window"
        >
          <header class="project-chat-window__header">
            <div class="project-chat-window__heading" @mousedown.stop>
              <strong :title="chatWindow.title">{{ chatWindow.title }}</strong>
              <span v-if="chatWindow.subtitle" :title="chatWindow.subtitle">{{ chatWindow.subtitle }}</span>
            </div>
            <div class="project-chat-window__actions">
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
              :project-id="chatWindow.projectId"
              :project-type="chatWindow.projectType"
              :active="!chatWindow.minimized"
              compact
              text-only
              always-enabled
              collapsible-filters
            />
          </div>
        </section>
      </div>

      <div v-if="state.windows.some(item => item.minimized)" class="project-chat-dock__taskbar">
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
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount } from 'vue'
import { ChatDotRound, Close, Minus } from '@element-plus/icons-vue'
import ProjectChatPanel from '@/components/ProjectChatPanel.vue'
import { useProjectChatDock } from '@/composables/useProjectChatDock'

const { state, closeChat, closeAllChats, minimizeChat, restoreChat } = useProjectChatDock()

onBeforeUnmount(closeAllChats)
</script>

<style scoped>
.project-chat-dock {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 2100;
  display: flex;
  max-width: calc(100vw - 32px);
  align-items: flex-end;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.project-chat-dock__windows {
  display: flex;
  max-width: calc(100vw - 32px);
  align-items: flex-end;
  gap: 12px;
  overflow-x: auto;
  padding: 4px;
  pointer-events: auto;
}

.project-chat-window {
  display: flex;
  width: min(410px, calc(100vw - 40px));
  height: min(680px, calc(100vh - 88px));
  flex: 0 0 min(410px, calc(100vw - 40px));
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  background: var(--el-bg-color);
  box-shadow: var(--el-box-shadow-dark);
}

.project-chat-window__header {
  display: flex;
  min-height: 48px;
  padding: 8px 10px 8px 14px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}

.project-chat-window__heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  cursor: text;
  user-select: text;
}

.project-chat-window__heading strong,
.project-chat-window__heading span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-chat-window__heading span {
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
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.project-chat-dock__taskbar {
  display: flex;
  max-width: calc(100vw - 32px);
  justify-content: flex-end;
  gap: 8px;
  overflow-x: auto;
  pointer-events: auto;
}

.project-chat-task {
  display: inline-flex;
  max-width: 260px;
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

@media (max-width: 768px) {
  .project-chat-dock {
    right: 8px;
    bottom: 8px;
    max-width: calc(100vw - 16px);
  }

  .project-chat-dock__windows,
  .project-chat-dock__taskbar {
    max-width: calc(100vw - 16px);
  }

  .project-chat-window {
    width: calc(100vw - 24px);
    height: calc(100vh - 72px);
    flex-basis: calc(100vw - 24px);
  }
}
</style>
