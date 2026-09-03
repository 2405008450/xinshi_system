<template>
  <div class="daily-report-panel">
    <div class="report-toolbar">
      <div class="toolbar-primary">
        <div class="toolbar-status">
          <el-tag size="small" :type="report.status === 'finalized' ? 'success' : 'info'">
            {{ report.status === 'finalized' ? '已确认' : '草稿' }}
          </el-tag>
          <el-tag v-if="dirtyCount" size="small" type="warning">{{ dirtyCount }} 行待保存</el-tag>
          <el-tag v-if="mailAccount.is_verified" size="small" type="success" effect="plain">个人邮箱已验证</el-tag>
          <el-tag v-else-if="mailAccount.is_bound" size="small" type="warning" effect="plain">邮箱待验证</el-tag>
        </div>
        <span v-if="editable" class="sheet-tip">
          <el-icon class="sheet-tip__icon"><InfoFilled /></el-icon>
          白底单元格可直接编辑并支持多格粘贴；灰底字段由系统生成。表格结构与来源字段已锁定。
        </span>
      </div>
      <div class="toolbar-actions">
        <el-button size="small" @click="openMailAccount">查看邮箱状态</el-button>
        <el-button v-if="editable" size="small" :loading="loading" @click="loadReport(true)">重新汇总</el-button>
        <el-button v-if="editable" size="small" @click="addManualItem">补充工作</el-button>
        <el-button v-if="editable && selectedIndexes.length" size="small" type="danger" plain @click="removeSelectedItems">删除选中补充行</el-button>
        <el-button v-if="editable" size="small" type="primary" plain :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button v-if="editable" size="small" type="success" :loading="saving" @click="save(true)">确认日报</el-button>
        <el-button v-if="report.status === 'finalized'" size="small" type="warning" plain :loading="saving" @click="withdrawReport">撤回确认</el-button>
        <el-button v-if="report.status === 'finalized'" size="small" type="primary" :loading="previewLoading" @click="openMailPreview">发送邮箱</el-button>
        <el-button size="small" :disabled="report.status !== 'finalized'" :loading="exporting" @click="downloadReport">导出 Excel</el-button>
      </div>
    </div>

    <DailyReportSpreadsheet
      ref="sheetRef"
      :rows="report.items"
      :editable="editable"
      :loading="loading"
      height="clamp(520px, calc(100vh - 300px), 900px)"
      @dirty-change="dirtyCount = $event"
      @selection-change="selectedIndexes = $event"
    />

    <section class="supplement-section">
      <button
        type="button"
        class="supplement-trigger"
        :aria-expanded="supplementExpanded"
        @click="supplementExpanded = !supplementExpanded"
      >
        <span class="supplement-trigger__title">补充说明</span>
        <span v-if="report.supplemental_note" class="supplement-trigger__status">已填写</span>
        <span class="supplement-trigger__hint">{{ supplementExpanded ? '收起' : '点击展开' }}</span>
        <el-icon class="supplement-trigger__arrow" :class="{ 'is-expanded': supplementExpanded }">
          <ArrowDown />
        </el-icon>
      </button>
      <el-collapse-transition>
        <AppForm v-show="supplementExpanded" label-position="top" class="supplement-form">
          <el-form-item>
            <el-input
              v-model="report.supplemental_note"
              type="textarea"
              :rows="3"
              maxlength="10000"
              show-word-limit
              :disabled="!editable"
              placeholder="可补充会议、沟通、异常情况或明日计划"
              @input="supplementDirty = true"
            />
          </el-form-item>
        </AppForm>
      </el-collapse-transition>
    </section>

    <el-dialog
      v-model="mailPreviewDialog"
      title="发送工作报告"
      width="min(1180px, calc(100vw - 32px))"
      top="5vh"
      class="daily-report-dialog mail-preview-dialog"
      destroy-on-close
      @closed="clearMailImageDraft"
    >
      <div v-loading="previewLoading" class="mail-preview-content">
        <el-alert
          v-if="mailPreview.delivery_mode === 'test'"
          :title="`测试模式：实际邮件只会发送到 ${mailPreview.test_recipient_masked || '测试收件箱'}`"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-alert
          v-if="mailPreview.blocking_reasons?.length"
          :title="mailPreview.blocking_reasons.join('；')"
          type="error"
          :closable="false"
          show-icon
        />
        <el-descriptions :column="2" border size="small" class="mail-meta">
          <el-descriptions-item label="发件人">{{ mailPreview.sender_name || '-' }} · {{ mailPreview.sender_email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="日报日期">{{ mailPreview.report_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="主送" :span="2">
            <el-tag v-for="item in mailPreview.to_users || []" :key="item.user_id" class="recipient-tag">{{ item.display_name }} · {{ item.email }}</el-tag>
            <span v-if="!mailPreview.to_users?.length">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="抄送" :span="2">
            <el-tag v-for="item in mailPreview.cc_users || []" :key="item.user_id" class="recipient-tag" type="info">{{ item.display_name }} · {{ item.email }}</el-tag>
            <span v-if="!mailPreview.cc_users?.length">-</span>
          </el-descriptions-item>
        </el-descriptions>
        <AppForm label-position="top" class="mail-form">
          <el-form-item label="邮件主题" required>
            <el-input v-model="mailPreview.subject" maxlength="1000" />
          </el-form-item>
          <el-form-item label="邮件正文表格（修改仅影响本次发送）">
            <DailyReportSpreadsheet
              ref="mailSheetRef"
              :rows="mailRows"
              mail-mode
              editable
              height="390px"
            />
          </el-form-item>
          <el-form-item label="正文图片（位于表格后、补充说明前）">
            <MailBodyEditor
              ref="mailBodyEditorRef"
              v-model:html-value="mailPreview.inline_image_html"
              :images="mailPreview.inline_images"
              image-only
              min-height="150px"
              @update:images="mailPreview.inline_images = $event"
              @uploading-change="mailImageUploading = $event"
            />
          </el-form-item>
          <el-form-item v-if="mailPreview.supplemental_note" label="补充说明（来自已确认日报）">
            <div class="readonly-note">{{ mailPreview.supplemental_note }}</div>
          </el-form-item>
          <el-form-item v-if="mailPreview.signature_html" label="邮件签名">
            <div class="mail-signature-preview" v-html="mailPreview.signature_html" />
          </el-form-item>
        </AppForm>
      </div>
      <template #footer>
        <el-button @click="mailPreviewDialog = false">取消</el-button>
        <el-button type="primary" :loading="sending" :disabled="mailImageUploading || !mailPreview.can_send || !mailPreview.subject?.trim()" @click="sendMail">确认发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import DailyReportSpreadsheet from './DailyReportSpreadsheet.vue'
import MailBodyEditor from '@/components/common/MailBodyEditor.vue'
import { getPersonalMailAccount } from '@/api/auth'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import {
  exportDailyReport,
  finalizeDailyReport,
  previewDailyReport,
  previewDailyReportMail,
  saveDailyReport,
  sendDailyReportMail,
  withdrawDailyReport
} from '@/api/tasks'

const props = defineProps({ reportDate: { type: String, required: true } })
const emit = defineEmits(['status-change'])
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const previewLoading = ref(false)
const sending = ref(false)
const dirtyCount = ref(0)
const supplementDirty = ref(false)
const supplementExpanded = ref(false)
const selectedIndexes = ref([])
const sheetRef = ref(null)
const mailSheetRef = ref(null)
const mailBodyEditorRef = ref(null)
const mailImageUploading = ref(false)
const mailPreviewDialog = ref(false)
const mailRows = ref([])
const report = reactive({ id: null, status: 'draft', supplemental_note: '', items: [] })
const mailAccount = reactive({ email: null, is_bound: false, is_verified: false, verified_at: null })
const mailPreview = reactive({
  report_id: null, report_date: '', sender_name: '', sender_email: null, subject: '', rows: [],
  supplemental_note: null, to_users: [], cc_users: [], can_send: false, blocking_reasons: [],
  inline_image_html: '', inline_images: [],
  signature_html: '', signature_text: '',
  delivery_mode: 'disabled', test_recipient_masked: null
})

const editable = computed(() => report.status !== 'finalized')
const hasUnsavedChanges = computed(() => dirtyCount.value > 0 || supplementDirty.value)

function applyReport(data) {
  report.id = data?.id || null
  report.status = data?.status || 'draft'
  report.supplemental_note = data?.supplemental_note || ''
  report.items = Array.isArray(data?.items) ? data.items.map(item => ({ ...item, duration_minutes: Number(item.duration_minutes || 0) })) : []
  dirtyCount.value = 0
  supplementDirty.value = false
  selectedIndexes.value = []
  emit('status-change', { date: props.reportDate, status: report.status })
}

function syncSheetRows() {
  if (sheetRef.value) report.items = sheetRef.value.getRows()
}

async function loadReport(refresh = false) {
  if (!props.reportDate) return
  if (refresh && hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('重新汇总会覆盖当前未保存修改，是否继续？', '重新汇总', { type: 'warning' })
    } catch { return }
  }
  loading.value = true
  try { applyReport(await previewDailyReport(props.reportDate, refresh === true)) }
  catch (error) { applyReport({}); ElMessage.error(error?.detail || '加载日报失败') }
  finally { loading.value = false }
}

function reportPayload() {
  syncSheetRows()
  return {
    supplemental_note: report.supplemental_note || null,
    items: report.items.map(({ id, sort_order, ...item }) => ({
      ...item,
      result_content: item.result_content || null,
      display_metadata: item.display_metadata || null
    }))
  }
}

async function save(finalize) {
  const payload = reportPayload()
  if (payload.items.some(item => !item.task_type?.trim() || !item.task_name?.trim() || !item.progress_content?.trim())) {
    ElMessage.warning('任务类型、任务名称和工作进展不能为空')
    return
  }
  try {
    if (finalize) await ElMessageBox.confirm('确认后将保存日报快照；邮件发送前仍可撤回确认，是否继续？', '确认日报', { type: 'warning' })
    saving.value = true
    applyReport(await (finalize ? finalizeDailyReport : saveDailyReport)(props.reportDate, payload))
    ElMessage.success(finalize ? '日报已确认' : '草稿已保存')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getLocalizedErrorMessage(error, '保存日报失败'))
  } finally { saving.value = false }
}

async function withdrawReport() {
  try {
    await ElMessageBox.confirm(
      '撤回后日报将恢复为草稿并重新汇总最新系统记录；如果邮件已经发送则不能撤回。是否继续？',
      '撤回确认',
      { type: 'warning', confirmButtonText: '确认撤回', cancelButtonText: '取消' }
    )
    saving.value = true
    await withdrawDailyReport(props.reportDate)
    await loadReport(true)
    ElMessage.success('日报已撤回为草稿')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getLocalizedErrorMessage(error, '撤回日报失败'))
    }
  } finally {
    saving.value = false
  }
}

function addManualItem() {
  syncSheetRows()
  report.items.push({
    source_type: 'manual', source_id: null, task_type: '其他', task_name: '', progress_content: '',
    result_content: '', duration_minutes: 0, display_metadata: null
  })
  supplementDirty.value = true
}

function removeSelectedItems() {
  syncSheetRows()
  const selected = new Set(selectedIndexes.value)
  const blocked = report.items.some((item, index) => selected.has(index) && item.source_type !== 'manual')
  if (blocked) return ElMessage.warning('系统汇总的工作不能在日报中删除，仅可删除手工补充行')
  report.items = report.items.filter((_item, index) => !selected.has(index))
  supplementDirty.value = true
}

async function downloadReport() {
  exporting.value = true
  try {
    const blob = await exportDailyReport(props.reportDate)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = `个人工作日报-${props.reportDate}.xlsx`
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '导出日报失败')) }
  finally { exporting.value = false }
}

async function loadMailAccount() {
  try { Object.assign(mailAccount, await getPersonalMailAccount()) }
  catch (error) { ElMessage.error(error?.detail || '读取个人邮箱状态失败') }
}

function openMailAccount() { router.push('/profile') }

function clearMailImageDraft() {
  mailBodyEditorRef.value?.cleanupDraftImages()
  mailPreview.inline_image_html = ''
  mailPreview.inline_images = []
}

async function openMailPreview() {
  previewLoading.value = true
  mailPreviewDialog.value = true
  try {
    const preview = await previewDailyReportMail(props.reportDate)
    Object.assign(mailPreview, preview)
    mailRows.value = (preview.rows || []).map(item => ({ ...item }))
  } catch (error) {
    mailPreviewDialog.value = false
    ElMessage.error(error?.detail || '加载邮件预览失败')
  } finally { previewLoading.value = false }
}

function idempotencyKey() {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `daily-report-${report.id || props.reportDate}-${random}`
}

async function sendMail() {
  const rows = mailSheetRef.value?.getRows?.() || mailRows.value
  try {
    await ElMessageBox.confirm(`确认以 ${mailPreview.sender_email} 向固定工作报告收件组发送邮件？`, '确认发送', { type: 'warning' })
    sending.value = true
    const result = await sendDailyReportMail(props.reportDate, {
      subject: mailPreview.subject.trim(), rows, supplemental_note: mailPreview.supplemental_note || null,
      inline_image_html: mailPreview.inline_image_html || null,
      inline_image_ids: mailPreview.inline_images.map(item => item.id),
      idempotency_key: idempotencyKey()
    })
    if (result.status === 'sent') {
      mailBodyEditorRef.value?.markImagesSaved()
      mailPreviewDialog.value = false
      ElMessage.success('工作报告邮件发送成功')
    } else ElMessage.error(result.send_error || '邮件发送失败，可重新打开预览后重试')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getLocalizedErrorMessage(error, '邮件发送失败'))
  } finally { sending.value = false }
}

function beforeUnload(event) {
  if (!hasUnsavedChanges.value) return
  event.preventDefault(); event.returnValue = ''
}

watch(() => props.reportDate, async () => {
  if (hasUnsavedChanges.value) ElMessage.warning('日期已切换，上一日期未保存的日报修改已放弃')
  supplementExpanded.value = false
  await loadReport(false)
})
onMounted(() => { loadReport(false); loadMailAccount(); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.daily-report-panel{min-width:0}.report-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}.toolbar-primary{display:flex;align-items:center;gap:10px;flex:1;min-width:0;flex-wrap:wrap}.toolbar-status,.toolbar-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.toolbar-actions{justify-content:flex-end;flex-shrink:0}.sheet-tip{display:inline-flex;align-items:center;gap:4px;font-size:12px;line-height:1.4;color:var(--el-color-info)}.sheet-tip__icon{flex-shrink:0;font-size:14px}.supplement-section{margin-top:8px;border:1px solid var(--el-border-color-lighter);border-radius:6px;background:var(--el-bg-color);overflow:hidden}.supplement-trigger{display:flex;align-items:center;width:100%;min-height:38px;padding:7px 12px;border:0;background:var(--el-fill-color-light);color:var(--el-text-color-primary);cursor:pointer;text-align:left}.supplement-trigger:hover{background:var(--el-fill-color)}.supplement-trigger:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}.supplement-trigger__title{font-size:14px;font-weight:600}.supplement-trigger__status{margin-left:8px;padding:1px 7px;border-radius:10px;background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-size:12px}.supplement-trigger__hint{margin-left:auto;color:var(--el-text-color-secondary);font-size:12px}.supplement-trigger__arrow{margin-left:6px;transition:transform .2s}.supplement-trigger__arrow.is-expanded{transform:rotate(180deg)}.supplement-form{padding:10px 12px 12px}.supplement-form :deep(.el-form-item){margin-bottom:0}.mail-meta{margin:14px 0}.recipient-tag{margin:2px 6px 2px 0}.mail-form{margin-top:14px}.mail-preview-content{min-height:300px}.readonly-note{width:100%;padding:10px 12px;border:1px solid var(--el-border-color);border-radius:6px;background:#f1f5f9;color:#475569;white-space:pre-wrap;word-break:break-word}:global(.daily-report-dialog){display:flex;max-height:90vh;overflow:hidden;flex-direction:column}:global(.daily-report-dialog .el-dialog__header),:global(.daily-report-dialog .el-dialog__footer){flex:none}:global(.daily-report-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.daily-report-dialog .el-dialog__footer){display:flex;align-items:center;border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}
.mail-signature-preview{width:100%;padding:10px 12px;border:1px solid var(--el-border-color);border-radius:6px;background:#f1f5f9;color:#475569;line-height:1.65;word-break:break-word}.mail-signature-preview :deep(p){margin:0 0 6px}
@media(max-width:768px){.report-toolbar{align-items:flex-start;flex-direction:column}.toolbar-primary{width:100%}.toolbar-actions{width:100%;justify-content:flex-start}.mail-meta{--el-descriptions-table-border:var(--el-border-color-lighter)}}
</style>
