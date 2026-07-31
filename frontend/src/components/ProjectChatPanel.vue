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
      <div class="chat-toolbar__hint">交接与继承记录始终可见；普通留言由管理员或项目经理开启。</div>

      <el-alert
        v-if="!settings.enabled"
        type="info"
        :closable="false"
        show-icon
        :title="settings.canManage ? '当前项目沟通未开启，可在右上角打开。' : '当前项目沟通未开启。'"
      />

      <template>
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
                  <el-tag v-if="message.messageType !== 'user'" size="small" :type="message.messageType === 'claim' ? 'warning' : 'success'" effect="plain">
                    {{ message.messageType === 'claim' ? '继承记录' : '交接记录' }}
                  </el-tag>
                  <el-tag v-if="message.mentionedUserName" size="small" type="warning" effect="plain">@{{ message.mentionedUserName }}</el-tag>
                </div>
                <span>{{ formatDateTime(message.createdAt) }}</span>
              </div>
              <RichTextContent :document="message.contentJson" :fallback="message.content" />
              <div v-if="message.metadata?.tasks?.length" class="handover-task-list">
                <div v-for="task in message.metadata.tasks" :key="task.workflowInstanceId">
                  <strong>{{ task.orderNo }}</strong>
                  <span>{{ task.taskName }}</span>
                  <span>{{ task.fromUserName }} → {{ task.toUserName }}</span>
                </div>
              </div>
              <div v-if="message.attachments?.length" class="message-attachments">
                <a
                  v-for="attachment in message.attachments"
                  :key="attachment.id"
                  :href="attachmentUrls[attachment.id] || undefined"
                  target="_blank"
                  rel="noopener"
                  class="message-attachment"
                >
                  <img v-if="attachmentUrls[attachment.id]" :src="attachmentUrls[attachment.id]" :alt="attachment.originalName" />
                  <span>{{ attachment.originalName }}</span>
                </a>
              </div>
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

        <div v-if="settings.enabled" class="chat-composer">
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
          <RichTextComposer
            v-model="composer.contentJson"
            placeholder="输入项目沟通内容…"
            @update:plain-text="composer.content = $event"
          />
          <div class="composer-attachments">
            <el-upload
              :show-file-list="false"
              :http-request="handleAttachmentUpload"
              accept="image/jpeg,image/png,image/gif,image/webp"
              multiple
            >
              <el-button :loading="uploading" :disabled="composer.attachments.length >= 9">添加图片</el-button>
            </el-upload>
            <el-tag
              v-for="attachment in composer.attachments"
              :key="attachment.id"
              closable
              @close="removeComposerAttachment(attachment.id)"
            >
              {{ attachment.originalName }}
            </el-tag>
          </div>
          <div class="chat-composer__actions">
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!composer.content.trim() && !composer.attachments.length"
              @click="handleSend"
            >
              发送消息
            </el-button>
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
import {
  createProjectChatMessage,
  getProjectChatAttachmentBlob,
  getProjectChatMessages,
  getProjectChatSettings,
  updateProjectChatSettings,
  uploadProjectChatAttachment
} from '@/api/projectChat'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'

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
const uploading = ref(false)
const userOptions = ref([])
const messages = ref([])
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const filters = reactive({ keyword: '', senderUserId: '', dateRange: [] })
const composer = reactive({
  content: '',
  contentJson: { type: 'doc', content: [{ type: 'paragraph' }] },
  mentionedUserId: '',
  attachments: []
})
const attachmentUrls = reactive({})
const attachmentObjectUrls = new Set()
const chatListMaxHeight = computed(() => (props.drawerMode ? 'calc(100vh - 360px)' : '420px'))
let pollTimer = null

const clearPolling = () => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const clearAttachmentUrls = () => {
  attachmentObjectUrls.forEach(url => URL.revokeObjectURL(url))
  attachmentObjectUrls.clear()
  Object.keys(attachmentUrls).forEach(key => delete attachmentUrls[key])
}

const ensureAttachmentUrls = async (items) => {
  const attachments = items.flatMap(item => item.attachments || [])
  await Promise.all(attachments.map(async (attachment) => {
    if (attachmentUrls[attachment.id]) return
    try {
      const blob = await getProjectChatAttachmentBlob(attachment.id)
      const url = URL.createObjectURL(blob)
      attachmentUrls[attachment.id] = url
      attachmentObjectUrls.add(url)
    } catch (error) {
      console.error('加载留言图片失败', error)
    }
  }))
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
  composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
  composer.mentionedUserId = ''
  composer.attachments = []
  clearAttachmentUrls()
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
  if (!props.projectId) {
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
    await ensureAttachmentUrls(messages.value)
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
  await loadMessages()
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
      pagination.page = 1
      await loadMessages()
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
  if (!props.projectId || (!composer.content.trim() && !composer.attachments.length)) return
  sending.value = true
  try {
    await createProjectChatMessage(props.projectId, {
      content: composer.content.trim(),
      contentJson: composer.contentJson,
      mentionedUserId: composer.mentionedUserId || undefined,
      attachmentIds: composer.attachments.map(item => item.id)
    })
    composer.content = ''
    composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
    composer.mentionedUserId = ''
    composer.attachments = []
    pagination.page = 1
    await loadMessages()
    ElMessage.success('消息已发送')
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '发送消息失败')
  } finally {
    sending.value = false
  }
}

const handleAttachmentUpload = async ({ file }) => {
  if (composer.attachments.length >= 9) {
    ElMessage.warning('每条留言最多添加 9 张图片')
    return
  }
  uploading.value = true
  try {
    const attachment = await uploadProjectChatAttachment(file)
    composer.attachments.push(attachment)
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '图片上传失败')
  } finally {
    uploading.value = false
  }
}

const removeComposerAttachment = (attachmentId) => {
  composer.attachments = composer.attachments.filter(item => item.id !== attachmentId)
}

const setupPolling = () => {
  clearPolling()
  if (!props.active || !props.projectId) return
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
  if (props.active && props.projectId) {
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
  clearAttachmentUrls()
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

.handover-task-list {
  display: grid;
  gap: 6px;
  margin-top: 10px;
  padding: 10px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  font-size: 12px;
}

.handover-task-list > div {
  display: grid;
  grid-template-columns: minmax(120px, 0.8fr) minmax(160px, 1.2fr) minmax(140px, 1fr);
  gap: 10px;
}

.message-attachments {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.message-attachment {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 132px;
  color: var(--el-color-primary);
  font-size: 12px;
  text-decoration: none;
}

.message-attachment img {
  width: 132px;
  height: 96px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
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

.composer-attachments {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

@media (max-width: 720px) {
  .handover-task-list > div {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>



