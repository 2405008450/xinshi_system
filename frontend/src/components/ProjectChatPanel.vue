<template>
  <div :class="['project-chat-panel', { 'project-chat-panel--drawer': drawerMode, 'project-chat-panel--compact': compact }]">
    <el-empty v-if="!projectId" description="请先选择项目" :image-size="compact ? 56 : 72" />
    <template v-else>
      <div class="chat-toolbar">
        <div class="chat-toolbar__title">
          <span>项目沟通</span>
          <el-tag v-if="!alwaysEnabled" :type="settings.enabled ? 'success' : 'info'" effect="plain">
            {{ settings.enabled ? '已开启' : '未开启' }}
          </el-tag>
        </div>
        <el-switch
          v-if="!alwaysEnabled && settings.canManage"
          v-model="settings.enabled"
          :loading="settingsLoading || toggleLoading"
          inline-prompt
          active-text="开"
          inactive-text="关"
          @change="handleToggle"
        />
      </div>
      <div v-if="!alwaysEnabled" class="chat-toolbar__hint">交接与继承记录始终可见；普通留言由管理员或项目经理开启。</div>

      <el-alert
        v-if="!alwaysEnabled && !settings.enabled"
        type="info"
        :closable="false"
        show-icon
        :title="settings.canManage ? '当前项目沟通未开启，可在右上角打开。' : '当前项目沟通未开启。'"
      />

      <AppForm :inline="true" :model="filters" size="small" class="chat-filter-bar">
          <el-form-item label="关键词" class="chat-filter-bar__field">
            <el-input v-model="filters.keyword" clearable :placeholder="compact ? '搜索消息内容' : '搜消息内容'" style="width: 180px" @keyup.enter="handleSearch" />
          </el-form-item>
          <el-form-item label="发送人" class="chat-filter-bar__field">
            <el-select v-model="filters.senderUserId" clearable filterable :placeholder="compact ? '发送人' : '全部'" style="width: 180px">
              <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围" class="chat-filter-bar__range">
            <el-date-picker
              v-model="filters.dateRange"
              type="datetimerange"
              value-format="YYYY-MM-DD HH:mm:ss"
              range-separator="至"
              start-placeholder="开始"
              end-placeholder="结束"
              format="YYYY-MM-DD HH:mm"
              time-format="HH:mm"
              :show-now="true"
              :show-confirm="true"
              :show-footer="true"
            />
          </el-form-item>
          <el-form-item class="chat-filter-bar__favorite">
            <el-checkbox v-model="filters.favoritesOnly" @change="handleSearch">只看收藏</el-checkbox>
          </el-form-item>
          <el-form-item class="chat-filter-bar__actions">
            <el-button type="primary" @click="handleSearch">查询</el-button>
            <el-button @click="handleResetSearch">重置</el-button>
          </el-form-item>
        </AppForm>

        <el-scrollbar v-loading="messagesLoading" :max-height="chatListMaxHeight" class="chat-list">
          <div v-if="messages.length" class="chat-list__items">
            <div v-for="message in messages" :key="message.id" class="chat-message-card">
              <div class="chat-message-card__meta">
                <div class="chat-message-card__author">
                  <strong>{{ message.senderName || '未知用户' }}</strong>
                  <el-tag v-if="message.messageType !== 'user'" size="small" :type="message.messageType === 'claim' ? 'warning' : 'success'" effect="plain">
                    {{ message.messageType === 'claim' ? '继承记录' : '交接记录' }}
                  </el-tag>
                  <el-tag
                    v-for="mention in messageMentions(message).slice(0, 3)"
                    :key="mention.mentionedUserId"
                    size="small"
                    type="warning"
                    effect="plain"
                  >
                    @{{ mention.mentionedUserName }}
                  </el-tag>
                  <el-tooltip
                    v-if="messageMentions(message).length > 3"
                    :content="messageMentions(message).slice(3).map(item => `@${item.mentionedUserName}`).join('、')"
                    placement="top"
                  >
                    <el-tag size="small" type="warning" effect="plain">+{{ messageMentions(message).length - 3 }}</el-tag>
                  </el-tooltip>
                </div>
                <div class="chat-message-card__tools">
                  <span>{{ formatDateTime(message.createdAt) }}</span>
                  <el-button
                    v-if="canAddToProgress && String(message.content || '').trim()"
                    type="primary"
                    link
                    size="small"
                    class="chat-message-card__progress-action"
                    @click="emit('add-to-progress', message)"
                  >
                    添加为进度
                  </el-button>
                  <el-tooltip :content="message.isFavorited ? '取消收藏（仅自己可见）' : '收藏（仅自己可见）'" placement="top">
                    <el-button
                      link
                      :type="message.isFavorited ? 'warning' : 'info'"
                      :loading="favoriteSavingIds.has(message.id)"
                      :aria-label="message.isFavorited ? '取消收藏' : '收藏'"
                      class="chat-message-card__favorite"
                      @click="handleFavoriteToggle(message)"
                    >
                      <el-icon><StarFilled v-if="message.isFavorited" /><Star v-else /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </div>
              <div v-if="textOnly" class="chat-message-card__content">{{ message.content }}</div>
              <RichTextContent v-else :document="message.contentJson" :fallback="message.content" />
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
          <el-empty v-else description="暂无沟通记录" :image-size="compact ? 56 : 72" />
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
          <div class="chat-composer__header">
            <span>发送消息</span>
            <div class="chat-composer__mention-wrap">
              <el-select
                v-model="composer.mentionedUserIds"
                multiple
                clearable
                filterable
                collapse-tags
                collapse-tags-tooltip
                :max-collapse-tags="compact ? 1 : 3"
                :multiple-limit="20"
                placeholder="@提醒用户（可多选）"
                class="chat-composer__mention"
              >
                <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
              </el-select>
              <span class="chat-composer__mention-count">{{ composer.mentionedUserIds.length }}/20</span>
            </div>
          </div>
          <div class="chat-composer__body">
            <el-input
              v-if="textOnly"
              v-model="composer.content"
              type="textarea"
              :autosize="compact ? { minRows: 2, maxRows: 4 } : false"
              :rows="compact ? undefined : 4"
              maxlength="10000"
              show-word-limit
              placeholder="输入项目沟通内容…"
            />
            <RichTextComposer
              v-else
              v-model="composer.contentJson"
              placeholder="输入项目沟通内容…"
              @update:plain-text="composer.content = $event"
            />
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
          <div v-if="!textOnly" class="composer-attachments">
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
        </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Star, StarFilled } from '@element-plus/icons-vue'
import { getUsers } from '@/api/users'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import {
  createProjectChatMessage,
  favoriteProjectChatMessage,
  getProjectChatAttachmentBlob,
  getProjectChatMessages,
  getProjectChatSettings,
  updateProjectChatSettings,
  unfavoriteProjectChatMessage,
  uploadProjectChatAttachment
} from '@/api/projectChat'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'

const props = defineProps({
  projectId: { type: [String, Number], default: '' },
  projectType: { type: String, default: 'translation' },
  active: { type: Boolean, default: false },
  drawerMode: { type: Boolean, default: false },
  textOnly: { type: Boolean, default: false },
  alwaysEnabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  canAddToProgress: { type: Boolean, default: false }
})

const emit = defineEmits(['add-to-progress'])

const settings = reactive({ enabled: false, canManage: false })
const settingsLoading = ref(false)
const toggleLoading = ref(false)
const messagesLoading = ref(false)
const sending = ref(false)
const uploading = ref(false)
const userOptions = ref([])
const messages = ref([])
const favoriteSavingIds = ref(new Set())
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const filters = reactive({ keyword: '', senderUserId: '', dateRange: [], favoritesOnly: false })
const composer = reactive({
  content: '',
  contentJson: { type: 'doc', content: [{ type: 'paragraph' }] },
  mentionedUserIds: [],
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

const resetChatState = () => {
  settings.enabled = props.alwaysEnabled
  settings.canManage = false
  messages.value = []
  pagination.page = 1
  pagination.limit = 20
  pagination.total = 0
  filters.keyword = ''
  filters.senderUserId = ''
  filters.dateRange = []
  filters.favoritesOnly = false
  composer.content = ''
  composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
  composer.mentionedUserIds = []
  composer.attachments = []
  clearAttachmentUrls()
  clearPolling()
}

const ensureUsersLoaded = async () => {
  if (userOptions.value.length) return
  try {
    const res = await getUsers({ skip: 0, limit: 500 })
    userOptions.value = Array.isArray(res)
      ? res.filter(user => user.isActive !== false && user.is_active !== false)
      : []
  } catch (error) {
    console.error('加载用户失败', error)
  }
}

const loadSettings = async () => {
  if (!props.projectId) return
  if (props.alwaysEnabled) {
    settings.enabled = true
    settings.canManage = false
    return
  }
  settingsLoading.value = true
  try {
    const res = await getProjectChatSettings(props.projectId)
    settings.enabled = !!res?.enabled
    settings.canManage = !!res?.canManage
  } catch (error) {
    settings.enabled = false
    settings.canManage = false
    ElMessage.error(getLocalizedErrorMessage(error, '加载项目沟通配置失败'))
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
      date_to: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[1] : undefined,
      favorites_only: filters.favoritesOnly || undefined
    }
    const res = await getProjectChatMessages(props.projectId, params, props.projectType)
    settings.enabled = !!res?.enabled
    if (typeof res?.canManage === 'boolean') settings.canManage = res.canManage
    messages.value = Array.isArray(res?.items) ? res.items : []
    pagination.total = Number(res?.total || 0)
    await ensureAttachmentUrls(messages.value)
  } catch (error) {
    messages.value = []
    pagination.total = 0
    ElMessage.error(getLocalizedErrorMessage(error, '加载沟通记录失败'))
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
    ElMessage.error(getLocalizedErrorMessage(error, '更新项目沟通配置失败'))
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
  filters.favoritesOnly = false
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
    const payload = props.textOnly
      ? {
          content: composer.content.trim(),
          mentionedUserIds: composer.mentionedUserIds
        }
      : {
          content: composer.content.trim(),
          contentJson: composer.contentJson,
          mentionedUserIds: composer.mentionedUserIds,
          attachmentIds: composer.attachments.map(item => item.id)
        }
    await createProjectChatMessage(props.projectId, payload, props.projectType)
    composer.content = ''
    composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
    composer.mentionedUserIds = []
    composer.attachments = []
    pagination.page = 1
    await loadMessages()
    ElMessage.success('消息已发送')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '发送消息失败'))
  } finally {
    sending.value = false
  }
}

const messageMentions = (message) => {
  if (Array.isArray(message?.mentions) && message.mentions.length) return message.mentions
  if (message?.mentionedUserId && message?.mentionedUserName) {
    return [{ mentionedUserId: message.mentionedUserId, mentionedUserName: message.mentionedUserName }]
  }
  return []
}

const handleFavoriteToggle = async (message) => {
  if (!message?.id || favoriteSavingIds.value.has(message.id)) return
  favoriteSavingIds.value = new Set([...favoriteSavingIds.value, message.id])
  const nextFavorited = !message.isFavorited
  try {
    const res = nextFavorited
      ? await favoriteProjectChatMessage(message.id)
      : await unfavoriteProjectChatMessage(message.id)
    message.isFavorited = !!res?.isFavorited
    message.favoritedAt = res?.favoritedAt || null
    if (filters.favoritesOnly && !message.isFavorited) {
      await loadMessages()
    }
    ElMessage.success(message.isFavorited ? '已收藏，仅自己可见' : '已取消收藏')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, nextFavorited ? '收藏消息失败' : '取消收藏失败'))
  } finally {
    const pending = new Set(favoriteSavingIds.value)
    pending.delete(message.id)
    favoriteSavingIds.value = pending
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
    ElMessage.error(getLocalizedErrorMessage(error, '图片上传失败'))
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

watch(() => [props.projectId, props.projectType], async () => {
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
  display: flex;
  align-items: center;
  gap: 8px 16px;
  flex-wrap: wrap;
  margin-bottom: 0;
}

.chat-filter-bar :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: 0;
}

.chat-filter-bar :deep(.el-form-item__label) {
  padding-right: 8px;
}

.chat-filter-bar__range :deep(.el-date-editor) {
  width: 360px;
}

.chat-filter-bar__actions {
  flex: none;
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
  flex-wrap: wrap;
}

.chat-message-card__tools {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}

.chat-message-card__favorite {
  padding: 2px;
  font-size: 17px;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  font-weight: 600;
}

.chat-composer__mention {
  width: 280px;
  font-weight: 400;
}

.chat-composer__mention-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.chat-composer__mention-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}

.chat-composer__body {
  min-width: 0;
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

.project-chat-panel--compact {
  gap: 10px;
  font-size: 14px;
}

.project-chat-panel--compact .chat-toolbar__title {
  font-size: 14px;
}

.project-chat-panel--compact .chat-filter-bar {
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
}

.project-chat-panel--compact .chat-filter-bar :deep(.el-form-item__label) {
  display: none;
}

.project-chat-panel--compact .chat-filter-bar__field :deep(.el-input) {
  width: 150px !important;
}

.project-chat-panel--compact .chat-filter-bar__field :deep(.el-select) {
  width: 130px !important;
}

.project-chat-panel--compact .chat-filter-bar__range :deep(.el-date-editor) {
  width: 250px;
}

.project-chat-panel--compact .chat-filter-bar__actions {
  margin-left: auto;
}

.project-chat-panel--compact .chat-list__items {
  gap: 8px;
  padding: 8px;
}

.project-chat-panel--compact .chat-message-card {
  padding: 10px 12px;
  border-radius: 6px;
}

.project-chat-panel--compact .chat-message-card__meta {
  margin-bottom: 5px;
}

.project-chat-panel--compact .chat-message-card__content {
  line-height: 1.5;
}

.project-chat-panel--compact .chat-composer {
  padding: 12px 14px;
  border-color: var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
}

.project-chat-panel--compact .chat-composer__header {
  margin-bottom: 10px;
  font-size: 14px;
}

.project-chat-panel--compact .chat-composer__mention {
  width: 220px;
}

.project-chat-panel--compact .chat-composer__body {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.project-chat-panel--compact .chat-composer__body > :first-child {
  min-width: 0;
  flex: 1;
}

.project-chat-panel--compact .chat-composer__actions {
  flex: none;
  margin-top: 0;
}

@media (max-width: 720px) {
  .chat-filter-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .chat-filter-bar :deep(.el-form-item) {
    display: flex;
    width: 100%;
  }

  .chat-filter-bar :deep(.el-form-item__content) {
    min-width: 0;
    flex: 1;
  }

  .chat-filter-bar__field :deep(.el-input),
  .chat-filter-bar__field :deep(.el-select),
  .chat-filter-bar__range :deep(.el-date-editor) {
    width: 100% !important;
  }

  .handover-task-list > div {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .project-chat-panel--compact .chat-filter-bar__field :deep(.el-input),
  .project-chat-panel--compact .chat-filter-bar__field :deep(.el-select),
  .project-chat-panel--compact .chat-filter-bar__range :deep(.el-date-editor) {
    width: 100% !important;
  }

  .project-chat-panel--compact .chat-filter-bar__actions {
    margin-left: 0;
  }

  .project-chat-panel--compact .chat-composer__header {
    align-items: stretch;
    flex-direction: column;
  }

  .project-chat-panel--compact .chat-composer__mention {
    width: 100%;
  }

  .chat-composer__mention-wrap {
    width: 100%;
  }

  .project-chat-panel--compact .chat-composer__body {
    align-items: stretch;
    flex-direction: column;
  }

  .project-chat-panel--compact .chat-composer__actions {
    justify-content: flex-end;
  }
}
</style>



