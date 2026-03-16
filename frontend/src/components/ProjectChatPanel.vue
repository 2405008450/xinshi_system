<template>
  <div :class="['project-chat-panel', { 'project-chat-panel--drawer': drawerMode }]">
    <el-empty v-if="!projectId" description="请先选择母订单项目" :image-size="72" />
    <template v-else>
      <div class="chat-toolbar">
        <div class="chat-toolbar__title">
          <span>项目沟通</span>
          <el-tag :type="settings.enabled ? 'success' : 'info'" effect="plain">
            {{ settings.enabled ? '已开启' : '未开启' }}
          </el-tag>
        </div>
        <el-switch
          v-if="settings.canManage"
          v-model="settings.enabled"
          :loading="settingsLoading || toggleLoading"
          inline-prompt
          active-text="开"
          inactive-text="关"
          @change="handleToggle"
        />
      </div>
      <div class="chat-toolbar__hint">所有系统账号均可查看和发送消息；仅管理员或项目经理可开启/关闭项目沟通。</div>

      <el-alert
        v-if="!settings.enabled"
        type="info"
        :closable="false"
        show-icon
        :title="settings.canManage ? '当前项目沟通未开启，可在右上角打开。' : '当前项目沟通未开启。'"
      />

      <template v-else>
        <el-form :inline="true" :model="filters" size="small" class="chat-filter-bar">
          <el-form-item label="关键词">
            <el-input v-model="filters.keyword" clearable placeholder="搜消息内容" style="width: 180px" @keyup.enter="handleSearch" />
          </el-form-item>
          <el-form-item label="发送人">
            <el-select v-model="filters.senderUserId" clearable filterable placeholder="全部" style="width: 180px">
              <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="filters.dateRange"
              type="datetimerange"
              value-format="YYYY-MM-DD HH:mm:ss"
              range-separator="至"
              start-placeholder="开始"
              end-placeholder="结束"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">查询</el-button>
            <el-button @click="handleResetSearch">重置</el-button>
          </el-form-item>
        </el-form>

        <el-scrollbar v-loading="messagesLoading" :max-height="chatListMaxHeight" class="chat-list">
          <div v-if="messages.length" class="chat-list__items">
            <div v-for="message in messages" :key="message.id" class="chat-message-card">
              <div class="chat-message-card__meta">
                <div class="chat-message-card__author">
                  <strong>{{ message.senderName || '未知用户' }}</strong>
                  <el-tag v-if="message.mentionedUserName" size="small" type="warning" effect="plain">@{{ message.mentionedUserName }}</el-tag>
                </div>
                <span>{{ formatDateTime(message.createdAt) }}</span>
              </div>
              <div class="chat-message-card__content">{{ message.content }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无沟通记录" :image-size="72" />
        </el-scrollbar>

        <div class="chat-pagination">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.limit"
            :page-sizes="[10, 20, 50]"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            small
            @current-change="loadMessages"
            @size-change="handlePageSizeChange"
          />
        </div>

        <div class="chat-composer">
          <div class="chat-composer__header">发送消息</div>
          <el-select
            v-model="composer.mentionedUserId"
            clearable
            filterable
            placeholder="@提醒某人（可选）"
            style="width: 280px; margin-bottom: 12px"
          >
            <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
          <el-input
            v-model="composer.content"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="输入项目沟通内容..."
          />
          <div class="chat-composer__actions">
            <el-button type="primary" :loading="sending" :disabled="!composer.content.trim()" @click="handleSend">发送消息</el-button>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getUsers } from '@/api/users'
import { createProjectChatMessage, getProjectChatMessages, getProjectChatSettings, updateProjectChatSettings } from '@/api/projectChat'

const props = defineProps({
  projectId: { type: [String, Number], default: '' },
  active: { type: Boolean, default: false },
  drawerMode: { type: Boolean, default: false }
})

const settings = reactive({ enabled: false, canManage: false })
const settingsLoading = ref(false)
const toggleLoading = ref(false)
const messagesLoading = ref(false)
const sending = ref(false)
const userOptions = ref([])
const messages = ref([])
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const filters = reactive({ keyword: '', senderUserId: '', dateRange: [] })
const composer = reactive({ content: '', mentionedUserId: '' })
const chatListMaxHeight = computed(() => (props.drawerMode ? 'calc(100vh - 360px)' : '420px'))
let pollTimer = null

const clearPolling = () => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

const resetChatState = () => {
  settings.enabled = false
  settings.canManage = false
  messages.value = []
  pagination.page = 1
  pagination.limit = 20
  pagination.total = 0
  filters.keyword = ''
  filters.senderUserId = ''
  filters.dateRange = []
  composer.content = ''
  composer.mentionedUserId = ''
  clearPolling()
}

const ensureUsersLoaded = async () => {
  if (userOptions.value.length) return
  try {
    const res = await getUsers({ skip: 0, limit: 500 })
    userOptions.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('加载用户失败', error)
  }
}

const loadSettings = async () => {
  if (!props.projectId) return
  settingsLoading.value = true
  try {
    const res = await getProjectChatSettings(props.projectId)
    settings.enabled = !!res?.enabled
    settings.canManage = !!res?.canManage
  } catch (error) {
    settings.enabled = false
    settings.canManage = false
    ElMessage.error(error?.detail || error?.message || '加载项目沟通配置失败')
  } finally {
    settingsLoading.value = false
  }
}

const loadMessages = async () => {
  if (!props.projectId || !settings.enabled) {
    messages.value = []
    pagination.total = 0
    return
  }
  messagesLoading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      keyword: filters.keyword || undefined,
      sender_user_id: filters.senderUserId || undefined,
      date_from: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[0] : undefined,
      date_to: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[1] : undefined
    }
    const res = await getProjectChatMessages(props.projectId, params)
    settings.enabled = !!res?.enabled
    if (typeof res?.canManage === 'boolean') settings.canManage = res.canManage
    messages.value = Array.isArray(res?.items) ? res.items : []
    pagination.total = Number(res?.total || 0)
  } catch (error) {
    messages.value = []
    pagination.total = 0
    ElMessage.error(error?.detail || error?.message || '加载沟通记录失败')
  } finally {
    messagesLoading.value = false
  }
}

const refreshChat = async () => {
  if (!props.projectId) return
  await Promise.all([loadSettings(), ensureUsersLoaded()])
  if (settings.enabled) {
    await loadMessages()
  } else {
    messages.value = []
    pagination.total = 0
  }
}

const handleToggle = async (enabled) => {
  if (!props.projectId) return
  toggleLoading.value = true
  try {
    const res = await updateProjectChatSettings(props.projectId, { enabled })
    settings.enabled = !!res?.enabled
    settings.canManage = !!res?.canManage
    if (settings.enabled) {
      pagination.page = 1
      await loadMessages()
    } else {
      messages.value = []
      pagination.total = 0
    }
    ElMessage.success(settings.enabled ? '已开启项目沟通' : '已关闭项目沟通')
  } catch (error) {
    settings.enabled = !enabled
    ElMessage.error(error?.detail || error?.message || '更新项目沟通配置失败')
  } finally {
    toggleLoading.value = false
    setupPolling()
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadMessages()
}

const handleResetSearch = () => {
  filters.keyword = ''
  filters.senderUserId = ''
  filters.dateRange = []
  pagination.page = 1
  loadMessages()
}

const handlePageSizeChange = () => {
  pagination.page = 1
  loadMessages()
}

const handleSend = async () => {
  if (!props.projectId || !composer.content.trim()) return
  sending.value = true
  try {
    await createProjectChatMessage(props.projectId, {
      content: composer.content.trim(),
      mentionedUserId: composer.mentionedUserId || undefined
    })
    composer.content = ''
    composer.mentionedUserId = ''
    pagination.page = 1
    await loadMessages()
    ElMessage.success('消息已发送')
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '发送消息失败')
  } finally {
    sending.value = false
  }
}

const setupPolling = () => {
  clearPolling()
  if (!props.active || !props.projectId || !settings.enabled) return
  pollTimer = window.setInterval(() => {
    loadMessages()
  }, 15000)
}

watch(() => props.projectId, async () => {
  resetChatState()
  if (props.projectId) {
    await refreshChat()
    setupPolling()
  }
}, { immediate: true })

watch(() => props.active, () => {
  setupPolling()
  if (props.active && props.projectId && settings.enabled) {
    loadMessages()
  }
})

watch(() => settings.enabled, () => {
  setupPolling()
})

onMounted(() => {
  ensureUsersLoaded()
})

onBeforeUnmount(() => {
  clearPolling()
})
</script>

<style scoped>
.project-chat-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-chat-panel--drawer {
  min-height: 100%;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.chat-toolbar__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.chat-toolbar__hint {
  margin-top: -8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.chat-filter-bar {
  margin-bottom: -6px;
}

.chat-list {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: #fff;
}

.chat-list__items {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.chat-message-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-fill-color-blank);
}

.chat-message-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.chat-message-card__author {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-primary);
}

.chat-message-card__content {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.chat-pagination {
  display: flex;
  justify-content: flex-end;
}

.chat-composer {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
  background: var(--el-fill-color-lighter);
}

.chat-composer__header {
  margin-bottom: 12px;
  font-weight: 600;
}

.chat-composer__actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>



