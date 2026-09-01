<template>
  <el-dialog
    v-model="visible"
    title="内部项目邮件预览"
    width="min(820px, calc(100vw - 32px))"
    top="5vh"
    class="business-mail-dialog"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="mail-composer-body">
      <el-alert
        v-if="preview.blocking_reasons?.length"
        :title="preview.blocking_reasons.join('；')"
        type="error"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="preview.missing_fields?.length"
        :title="`以下核心字段尚未填写：${preview.missing_fields.join('、')}`"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-descriptions :column="1" border size="small" class="sender-summary">
        <el-descriptions-item label="发件人">
          {{ preview.sender_name || '未识别' }}
          <span v-if="preview.sender_email"> · {{ preview.sender_email }}</span>
          <el-tag
            v-if="preview.sender_mode === 'personal'"
            size="small"
            :type="preview.sender_verified ? 'success' : 'warning'"
            effect="plain"
          >个人邮箱</el-tag>
          <el-button
            v-if="preview.sender_mode === 'personal' && !preview.sender_verified"
            type="primary"
            link
            @click="openProfile"
          >查看发件邮箱状态</el-button>
        </el-descriptions-item>
      </el-descriptions>
      <el-form label-width="92px" @submit.prevent>
        <el-form-item label="收件人" required>
          <InternalMailRecipientSelector
            v-model="form.toUserIds"
            :users="availableUsers"
            :groups="recipientGroups"
            placeholder="请选择收件人"
          />
        </el-form-item>
        <el-form-item label="抄送">
          <InternalMailRecipientSelector
            v-model="form.ccUserIds"
            :users="availableUsers"
            :groups="recipientGroups"
            :excluded-user-ids="form.toUserIds"
            placeholder="请选择抄送人"
          />
        </el-form-item>
        <el-form-item label="邮件主题" required>
          <div class="subject-field">
            <el-input
              v-model="form.subject"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 3 }"
              resize="none"
              :maxlength="SUBJECT_MAX_LENGTH"
            />
            <div
              class="subject-character-count"
              :class="{ 'near-limit': subjectCharacterCount >= SUBJECT_WARNING_LENGTH }"
            >
              {{ subjectCharacterCount }} / {{ SUBJECT_MAX_LENGTH }} 字符
            </div>
          </div>
        </el-form-item>
        <el-form-item label="邮件正文" required>
          <MailBodyEditor
            ref="bodyEditorRef"
            v-model="form.body"
            v-model:html-value="form.bodyHtml"
            :images="form.inlineImages"
            @update:images="form.inlineImages = $event"
            @uploading-change="imageUploading = $event"
          />
        </el-form-item>
      </el-form>
      <div v-if="history.length" class="mail-history-hint">
        上次发送：{{ formatDateTime(history[0].sent_at || history[0].send_attempted_at) }}，
        发件人：{{ history[0].sender_name || '历史未记录' }}<span v-if="history[0].sender_email"> · {{ history[0].sender_email }}</span>，
        状态：{{ statusLabel(history[0].status) }}
      </div>
    </div>
    <template #footer>
      <el-button :disabled="sending" @click="visible = false">取消</el-button>
      <el-button
        v-if="latestFailedMail"
        :loading="sending"
        :disabled="!preview.can_send"
        @click="retryFailedMail"
      >重试失败邮件</el-button>
      <el-button type="primary" :loading="sending" :disabled="!canSubmit" @click="submitMail">
        {{ history.some((item) => item.status === 'sent') ? '再次发送邮件' : '发送邮件' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as mailApi from '@/api/businessMails'
import * as userApi from '@/api/users'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import InternalMailRecipientSelector from '@/components/common/InternalMailRecipientSelector.vue'
import MailBodyEditor from '@/components/common/MailBodyEditor.vue'

const props = defineProps({
  modelValue: Boolean,
  projectType: { type: String, required: true },
  projectId: { type: String, required: true },
  consultationId: { type: String, default: '' },
  sourceKind: { type: String, default: 'project_manual' },
})
const emit = defineEmits(['update:modelValue', 'sent'])
const router = useRouter()
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })
const loading = ref(false)
const sending = ref(false)
const preview = reactive({
  missing_fields: [], blocking_reasons: [], can_send: false,
  sender_mode: 'system', sender_name: '', sender_email: '', sender_verified: false,
})
const form = reactive({ toUserIds: [], ccUserIds: [], subject: '', body: '', bodyHtml: '', inlineImages: [] })
const bodyEditorRef = ref(null)
const imageUploading = ref(false)
const availableUsers = ref([])
const recipientGroups = ref([])
const history = ref([])
const SUBJECT_MAX_LENGTH = 120
const SUBJECT_WARNING_LENGTH = 100

const canSubmit = computed(() => !imageUploading.value && preview.can_send && form.toUserIds.length > 0 && form.subject.trim() && form.body.trim())
const subjectCharacterCount = computed(() => Array.from(form.subject || '').length)
const selectedRecipientCount = computed(() => new Set([...form.toUserIds, ...form.ccUserIds]).size)
const isAllMembersSelected = computed(() => availableUsers.value.length > 1 && selectedRecipientCount.value >= availableUsers.value.length)
const latestFailedMail = computed(() => history.value[0]?.status === 'failed' ? history.value[0] : null)
const statusLabel = (value) => ({ sent: '已发送', failed: '发送失败', pending: '待发送', sending: '发送中' }[value] || value)
const makeIdempotencyKey = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
const openProfile = () => { visible.value = false; router.push('/profile') }

const loadPreview = async () => {
  if (!props.projectId) return
  loading.value = true
  try {
    const [mailPreview, users, groups, rows] = await Promise.all([
      mailApi.previewProjectMail({ project_type: props.projectType, project_id: props.projectId }),
      userApi.getUsers({ skip: 0, limit: 500 }),
      mailApi.getAvailableMailGroups(),
      mailApi.getProjectMailHistory({ project_type: props.projectType, project_id: props.projectId }),
    ])
    Object.assign(preview, mailPreview)
    form.toUserIds = mailPreview.to_users.map((item) => item.user_id)
    form.ccUserIds = mailPreview.cc_users.map((item) => item.user_id)
    form.subject = mailPreview.subject || ''
    form.body = mailPreview.body || ''
    form.bodyHtml = mailPreview.body_html || ''
    form.inlineImages = mailPreview.inline_images || []
    availableUsers.value = (users || []).filter((item) => item.is_active && item.email)
    recipientGroups.value = groups || []
    history.value = rows || []
  } catch (error) {
    ElMessage.error(error.detail || '加载邮件预览失败')
  } finally {
    loading.value = false
  }
}

watch(visible, (isVisible) => {
  if (isVisible) loadPreview()
}, { immediate: true })

const submitMail = async () => {
  if (!canSubmit.value) return
  const warnings = []
  if (isAllMembersSelected.value) warnings.push(`本邮件将发送给全体 ${availableUsers.value.length} 名内部成员`)
  if (history.value.some((item) => item.status === 'sent')) warnings.push('该项目已有成功发送记录，本次会再次发送一封新邮件')
  if (warnings.length) {
    try {
      await ElMessageBox.confirm(`${warnings.join('；')}。确认继续吗？`, '发送范围确认', { type: 'warning' })
    } catch { return }
  }
  sending.value = true
  try {
    const result = await mailApi.sendProjectMail({
      project_type: props.projectType,
      project_id: props.projectId,
      consultation_id: props.consultationId || null,
      source_kind: props.sourceKind,
      to_user_ids: form.toUserIds,
      cc_user_ids: form.ccUserIds.filter((id) => !form.toUserIds.includes(id)),
      subject: form.subject.trim(),
      body: form.body.trim(),
      body_html: form.bodyHtml || null,
      inline_image_ids: form.inlineImages.map(item => item.id),
      idempotency_key: makeIdempotencyKey(),
    })
    if (result.status === 'sent') {
      bodyEditorRef.value?.markImagesSaved()
      ElMessage.success('内部项目邮件已发送')
      visible.value = false
    } else {
      ElMessage.error(`项目已保存，但邮件发送失败：${result.send_error || '未知错误'}`)
    }
    emit('sent', result)
  } catch (error) {
    ElMessage.error(error.detail || '发送邮件失败')
  } finally {
    sending.value = false
  }
}

watch(visible, (isVisible, wasVisible) => {
  if (!isVisible && wasVisible) bodyEditorRef.value?.cleanupDraftImages()
})

const retryFailedMail = async () => {
  if (!latestFailedMail.value || !preview.can_send) return
  sending.value = true
  try {
    const result = await mailApi.retryProjectMail(latestFailedMail.value.id)
    if (result.status === 'sent') {
      ElMessage.success('失败邮件已使用当前账号重新发送')
      visible.value = false
    } else {
      ElMessage.error(result.send_error || '邮件重试失败')
    }
    emit('sent', result)
  } catch (error) {
    ElMessage.error(error.detail || '邮件重试失败')
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.mail-composer-body { display: flex; flex-direction: column; gap: 14px; }
.mail-history-hint { padding: 10px 12px; border-radius: 6px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); font-size: 13px; }
.sender-summary :deep(.el-tag) { margin-left: 8px; }
.subject-field { width: 100%; min-width: 0; }
.subject-character-count { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; text-align: right; white-space: nowrap; }
.subject-character-count.near-limit { color: var(--el-color-warning); font-weight: 600; }
:global(.business-mail-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.business-mail-dialog .el-dialog__header), :global(.business-mail-dialog .el-dialog__footer) { flex-shrink: 0; }
:global(.business-mail-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
</style>
