<template>
  <div class="daily-report-panel" data-auto-draft="off" data-screenshot-editor="own" @paste.capture="blockReportImages" @drop.capture="blockReportImages">
    <div class="report-identity">
      <div class="report-date"><span>日期</span><el-button :disabled="saving||loading" @click="changeDate(shiftReportDate(reportDate,-1))">前一天</el-button><el-date-picker :model-value="reportDate" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" :clearable="false" :disabled="saving||loading" aria-label="工作报告日期" @update:model-value="changeDate" /><strong>{{reportWeekday(reportDate)}}</strong><el-button :disabled="saving||loading" @click="changeDate(shiftReportDate(reportDate,1))">后一天</el-button><el-button :disabled="saving||loading" @click="changeDate(reportBusinessDate())">今天</el-button></div>
      <div>姓名：<strong>{{editorContext.user_name||report.user_name||'-'}}</strong></div><div class="report-departments">部门：<el-tag v-for="name in editorContext.departments" :key="name" effect="plain">{{name}}</el-tag><span v-if="!editorContext.departments.length">未设置部门</span></div>
    </div>
    <div class="report-toolbar">
      <div class="toolbar-primary">
        <div class="toolbar-status">
          <el-tag size="small" :type="report.status === 'finalized' ? 'success' : 'info'">
            {{ report.status === 'finalized' ? '已确认' : '草稿' }}
          </el-tag>
          <el-tag v-if="dirtyCount" size="small" :type="reportCloud.state==='synced'?'success':'warning'">{{reportCloud.state==='synced'?'草稿已自动保存':'编辑内容待同步'}}</el-tag>
          <el-tag v-if="mailAccount.is_verified" size="small" type="success" effect="plain">个人邮箱已验证</el-tag>
          <el-tag v-else-if="mailAccount.is_bound" size="small" type="warning" effect="plain">邮箱待验证</el-tag>
        </div>
        <span v-if="editable" class="sheet-tip">
          <el-icon class="sheet-tip__icon"><InfoFilled /></el-icon>
          直接填写单元格，Tab 切换；重复订单归入二级，系统记录为灰底只读。每天早上 07:00 换日。
        </span>
      </div>
      <div class="toolbar-actions">
        <el-button size="small" @click="openMailAccount">查看邮箱状态</el-button>
        <el-button v-if="editable&&!amending" size="small" :loading="loading" @click="loadReport(true)">重新汇总</el-button>
        <el-button v-if="editable" size="small" @click="sheetRef?.add()">新增一行</el-button>
        <el-button v-if="editable&&!amending" size="small" type="primary" plain :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button v-if="editable" size="small" type="success" :loading="saving" @click="save(true)">{{amending?'保存一次修订':'确认报告'}}</el-button>
        <el-button v-if="report.can_amend&&!amending" size="small" type="warning" plain @click="amending=true">修改一次</el-button><el-button v-if="amending" size="small" :disabled="saving" @click="loadReport(false)">取消修订</el-button>
        <el-button v-if="report.status === 'finalized'&&!amending" size="small" type="primary" :loading="previewLoading" @click="openMailPreview">{{report.amendment_used?'再次发送邮箱':'发送邮箱'}}</el-button>
        <el-button size="small" :disabled="report.status !== 'finalized'" :loading="exporting" @click="downloadReport">导出 Excel</el-button>
      </div>
    </div>

    <div class="report-autosave-state" role="status">{{autosaveLabel}}</div><el-alert v-if="localDraftError||reportCloud.error" :title="localDraftError||reportCloud.error" type="warning" :closable="false" />
    <ReportIdleTime ref="idleTimeRef" :report-date="reportDate" v-model:minutes="report.idle_minutes" v-model:confirmed="report.idle_declaration_confirmed" :declaration-text="report.idle_declaration_text||''" :editable="editable&&!saving" @change="onIdleChange" />
    <DailyReportEditor ref="sheetRef" :rows="report.items" :editable="editable && !saving" :loading="loading" :history="taskHistory" :categories="editorContext.work_categories" :layout-department="editorContext.is_layout_department" :task-presets="editorContext.layout_task_presets" :can-add-project-category="editorContext.can_add_project_category" :category-storage-ready="editorContext.category_storage_ready" @categories-change="Object.assign(editorContext,$event)" @dirty-change="onEditorChange" @remember="rememberTask" />

    <ReportRevisionHistory v-if="report.id" :report-id="report.id" :version="report.amendment_used" />
    <section v-if="report.id" class="report-feedback-section"><ReportFeedbackPanel :key="report.id" :report-id="report.id" /></section>
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
              :disabled="!editable || saving"
              placeholder="可补充会议、沟通、异常情况或明日计划"
              @input="supplementDirty = true;onEditorChange(dirtyCount)"
            />
          </el-form-item>
        </AppForm>
      </el-collapse-transition>
    </section>

    <DraggableFormDialog
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
          <ReportIdleTime v-if="mailPreview.idle_minutes!=null" :minutes="mailPreview.idle_minutes" :confirmed="mailPreview.idle_declaration_confirmed" :declaration-text="mailPreview.idle_declaration_text||''" />
          <el-form-item v-if="mailPreview.supplemental_note" label="补充说明（来自已确认报告）">
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
    </DraggableFormDialog>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import DailyReportEditor from './DailyReportEditor.vue'
import ReportIdleTime from './ReportIdleTime.vue'
import ReportFeedbackPanel from './ReportFeedbackPanel.vue'
import ReportRevisionHistory from './ReportRevisionHistory.vue'
import {subscribe} from '@/utils/realtimeSocket'
import {readCloudDraft,queueCloudDraft,cloudDraftStatus,acknowledgeCloudDraft} from '@/utils/cloudDrafts'
import {chooseDraft} from '@/utils/draftRecovery'
import {createAutoDraftStore} from '@/utils/autoDraftStore'
import {reportBusinessDate,reportWeekday,shiftReportDate,blockReportImages,requiresProjectIdentity} from '@/utils/workReportForm'
import { getPersonalMailAccount } from '@/api/auth'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import {
  getDailyReportEditorContext,
  amendDailyReport,
  exportDailyReport,
  finalizeDailyReport,
  previewDailyReport,
  previewDailyReportMail,
  saveDailyReport,
  sendDailyReportMail
} from '@/api/tasks'

const DailyReportSpreadsheet = defineAsyncComponent(() => import('./DailyReportSpreadsheet.vue'))
const MailBodyEditor = defineAsyncComponent(() => import('@/components/common/MailBodyEditor.vue'))

const props = defineProps({ reportDate: { type: String, required: true } })
const emit = defineEmits(['status-change','update:report-date'])
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const previewLoading = ref(false)
const sending = ref(false)
const dirtyCount = ref(0)
const supplementDirty = ref(false)
const supplementExpanded = ref(false)
const sheetRef = ref(null)
const mailSheetRef = ref(null)
const mailBodyEditorRef = ref(null)
const mailImageUploading = ref(false)
const mailPreviewDialog = ref(false)
const mailRows = ref([])
const localDraftError=ref('')
const reportCloud=computed(()=>cloudDraftStatus('work-report',props.reportDate))
const autosaveLabel=computed(()=>localDraftError.value||reportCloud.value.error?'自动保存异常，本机内容仍保留':reportCloud.value.state==='synced'?'草稿已同步云端':reportCloud.value.state==='saving'?'正在同步云端…':hasUnsavedChanges.value?'已在本机备份，等待同步云端':'自动保存已开启：本机400毫秒，云端约3秒')
const idleTimeRef=ref()
const report = reactive({idle_minutes:null,idle_declaration_confirmed:false,idle_declaration_text:null, can_amend:false,amendment_used:false,user_name: '', id: null, status: 'draft', supplemental_note: '', items: [] })
const mailAccount = reactive({ email: null, is_bound: false, is_verified: false, verified_at: null })
const mailPreview = reactive({
  report_id: null, report_date: '', sender_name: '', sender_email: null, subject: '', rows: [],
  supplemental_note: null, to_users: [], cc_users: [], can_send: false, blocking_reasons: [],
  inline_image_html: '', inline_images: [],
  signature_html: '', signature_text: '',
  delivery_mode: 'disabled', test_recipient_masked: null
})

const amending=ref(false)
const loadedDate=ref('')
const editable = computed(() => (report.status !== 'finalized'||amending.value) && loadedDate.value===props.reportDate)
const hasUnsavedChanges = computed(() => dirtyCount.value > 0 || supplementDirty.value)

function applyReport(data) {
  amending.value=false
  report.can_amend=!!data?.can_amend
  report.amendment_used=!!data?.amendment_used
  loadedDate.value=data?.report_date||props.reportDate
  report.user_name = data?.user_name || ''
  report.id = data?.id || null
  report.status = data?.status || 'draft'
  report.supplemental_note = data?.supplemental_note || ''
  report.idle_minutes=data?.idle_minutes??null
  report.idle_declaration_confirmed=data?.idle_declaration_confirmed===true
  report.idle_declaration_text=data?.idle_declaration_text||null
  report.items = Array.isArray(data?.items) ? data.items.map(item => ({ ...item, duration_minutes: Number(item.duration_minutes || 0) })) : []
  dirtyCount.value = 0
  supplementDirty.value = false
  nextTick(()=>{dirtyCount.value=0;supplementDirty.value=false})
  emit('status-change', { date: props.reportDate, status: report.status })
}

function syncSheetRows() {
  if (sheetRef.value) report.items = sheetRef.value.getRows()
}

let loadSequence=0,loadController
async function loadReport(refresh = false) {
  if (!props.reportDate) return
  if(refresh&&hasUnsavedChanges.value){try{await ElMessageBox.confirm('重新汇总会覆盖当前未保存修改，是否继续？','重新汇总',{type:'warning'})}catch{return}}
  const sequence=++loadSequence,date=props.reportDate
  loadController?.abort();loadController=new AbortController();loading.value=true
  try {
    const [data,cloud]=await Promise.all([previewDailyReport(date,refresh===true,{signal:loadController.signal}),readCloudDraft('work-report',date).catch(()=>null)])
    if(sequence!==loadSequence)return
    applyReport(data)
    let local
    try{local=JSON.parse(localStorage.getItem(draftKey(date))||'null')}catch{/* 保留损坏数据，不覆盖原始备份。 */}
    let draft=chooseDraft(local,cloud)
    if(draft?.report_date&&draft.report_date!==date)draft=null
    if(!draft&&!cloud?.revision&&!data.id&&!data.items?.length){
      // 兼容旧版通用草稿：仅在原日期且服务器无报告内容时带回，原草稿继续保留。
      const legacy=createAutoDraftStore({storage:localStorage,owner}).list().find(record=>record.route?.includes('/workbench')&&Array.isArray(record.data?.rows)&&record.data.rows.length&&record.data.rows.every(row=>row.source_type&&row.display_metadata)&&reportBusinessDate(new Date(record.time))===date)
      if(legacy)draft={items:legacy.data.rows,_savedAt:legacy.time}
    }
    const restoreAllowed=data.status!=='finalized'||(draft?.amending===true&&data.can_amend)
    if(draft&&restoreAllowed){
      if(draft.amending)amending.value=true
      report.items=Array.isArray(draft.items)?draft.items:report.items
      report.supplemental_note=draft.supplemental_note||''
      report.idle_minutes=draft.idle_minutes??null
      report.idle_declaration_confirmed=draft.idle_declaration_confirmed===true
      await nextTick();dirtyCount.value=1
      if(draft===local&&cloud)queueCloudDraft('work-report',date,autoDraftPayload(date))
    }

  }catch(error){if(sequence===loadSequence&&error?.code!=='ERR_CANCELED'){loadedDate.value='';ElMessage.error(error?.detail||'加载工作报告失败')}}
  finally{if(sequence===loadSequence)loading.value=false}
}
const editorContext=reactive({user_name:'',departments:[]})
const owner=localStorage.getItem('user_id')||'anonymous'
const historyKey=`daily-report-task-history:${owner}`
const draftKey=date=>`daily-report-form-draft:${owner}:${date}`
const taskHistory=ref([])
try{const saved=JSON.parse(localStorage.getItem(historyKey)||'[]');if(Array.isArray(saved))taskHistory.value=saved.filter(value=>typeof value==='string').slice(0,200)}catch{/* 本地存储不可用时仍可编辑。 */}
function rememberTask(value){if(!value?.trim())return;taskHistory.value=[value,...taskHistory.value.filter(item=>item!==value)].slice(0,200);try{localStorage.setItem(historyKey,JSON.stringify(taskHistory.value))}catch{/* 保留会话内历史。 */}}
function autoDraftPayload(date){return {report_date:date,amending:amending.value,items:sheetRef.value?.getRows()||report.items,supplemental_note:report.supplemental_note,idle_minutes:report.idle_minutes,idle_declaration_confirmed:report.idle_declaration_confirmed}}
function cacheDraft(date=props.reportDate){
 if((report.status==='finalized'&&!amending.value)||loadedDate.value!==date||!hasUnsavedChanges.value)return
 const value=autoDraftPayload(date)
 try{
  const previous=JSON.parse(localStorage.getItem(draftKey(date))||'null')
  if(!previous||JSON.stringify({...previous,_savedAt:undefined})!==JSON.stringify(value))localStorage.setItem(draftKey(date),JSON.stringify({...value,_savedAt:Date.now()}))
  localDraftError.value=''
 }catch{localDraftError.value='浏览器备份失败，请检查存储空间；正在尝试同步云端'}
 queueCloudDraft('work-report',date,value)
}
let draftTimer
function onIdleChange(){supplementDirty.value=true;clearTimeout(draftTimer);draftTimer=setTimeout(()=>cacheDraft(),400)}
function onEditorChange(count){dirtyCount.value=count;clearTimeout(draftTimer);draftTimer=setTimeout(()=>cacheDraft(),400)}
function changeDate(date){if(!date||date===props.reportDate)return;clearTimeout(draftTimer);cacheDraft();emit('update:report-date',date)}
async function loadEditorContext(){try{const data=await getDailyReportEditorContext();Object.assign(editorContext,data);taskHistory.value=[...new Set([...taskHistory.value,...(data.task_history||[])])].slice(0,200)}catch(error){ElMessage.error(error?.detail||'读取姓名与部门失败')}}

function reportPayload() {
  syncSheetRows()
  return {
    supplemental_note: report.supplemental_note || null,
    idle_minutes:report.idle_minutes,
    idle_declaration_confirmed:report.idle_declaration_confirmed,
    items: report.items.map(({ id, sort_order, ...item }) => ({
      ...item,
      result_content: item.result_content || null,
      display_metadata: item.display_metadata || null
    }))
  }
}

async function save(finalize) {
  if(saving.value||loading.value||!editable.value)return
  const date=props.reportDate
  if(!await idleTimeRef.value?.validate().catch(()=>false))return
  if(!await sheetRef.value?.validate().catch(()=>false)||date!==props.reportDate)return
  const payload = reportPayload()
  if (payload.items.some(item => !item.task_type?.trim() || (requiresProjectIdentity(item)&&!item.task_name?.trim()) || !item.progress_content?.trim())) {
    ElMessage.warning('请补全任务类型、具体任务及必填的项目名称')
    return
  }
  try {
    if (finalize) await ElMessageBox.confirm(amending.value?'保存后将用完本日报告的一次修改机会，修改记录对查看人可见。是否保存？':'确认后将保存工作报告，仅有一次修订机会，是否继续？', '确认报告', { type: 'warning' })
    if (saving.value||date!==props.reportDate) return
    saving.value = true
    const data=await (amending.value?amendDailyReport:finalize?finalizeDailyReport:saveDailyReport)(date, payload)
    try{localStorage.removeItem(draftKey(date))}catch{/* 不影响数据库保存结果。 */}
    acknowledgeCloudDraft('work-report',date,data.edit_draft_revision||0)
    if(date===props.reportDate)applyReport(data)
    if(data.status==='finalized')window.dispatchEvent(new Event('work-report-lunch-changed'))
    ElMessage.success(finalize ? '报告已确认' : '草稿已保存')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getLocalizedErrorMessage(error, '保存日报失败'))
  } finally { saving.value = false }
}

async function downloadReport() {
  exporting.value = true
  try {
    const blob = await exportDailyReport(props.reportDate)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = `我的工作报告-${props.reportDate}.xlsx`
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

function onReportHidden(){if(document.hidden)cacheDraft()}
function beforeUnload() {
  if (!hasUnsavedChanges.value) return
  cacheDraft()
}

watch(() => props.reportDate, async (_date,previousDate) => {
  clearTimeout(draftTimer);cacheDraft(previousDate)
  supplementExpanded.value = false
  await loadReport(false)
})
const stopUpdates=subscribe('daily_report_updated',event=>{if(event.user_id!==owner||event.report_date!==props.reportDate)return;if(hasUnsavedChanges.value)ElMessage.info('新咨询工作项已追加，保存当前修改时会自动保留');else loadReport(false)})
onMounted(() => { loadReport(false); loadMailAccount(); loadEditorContext(); window.addEventListener('beforeunload', beforeUnload);document.addEventListener('visibilitychange',onReportHidden) })
onBeforeUnmount(() => {stopUpdates();cacheDraft();clearTimeout(draftTimer);loadSequence++;loadController?.abort();window.removeEventListener('beforeunload', beforeUnload);document.removeEventListener('visibilitychange',onReportHidden)})
</script>

<style scoped>
.report-identity{display:flex;flex-wrap:wrap;gap:14px 24px;align-items:center;padding:12px 0 16px}.report-date{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.report-date :deep(.el-date-editor){width:150px}.report-departments{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.daily-report-panel{min-width:0}.report-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}.toolbar-primary{display:flex;align-items:center;gap:10px;flex:1;min-width:0;flex-wrap:wrap}.toolbar-status,.toolbar-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.toolbar-actions{justify-content:flex-end;flex-shrink:0}.sheet-tip{display:inline-flex;align-items:center;gap:4px;font-size:12px;line-height:1.4;color:var(--el-color-info)}.sheet-tip__icon{flex-shrink:0;font-size:14px}.supplement-section{margin-top:8px;border:1px solid var(--el-border-color-lighter);border-radius:6px;background:var(--el-bg-color);overflow:hidden}.supplement-trigger{display:flex;align-items:center;width:100%;min-height:38px;padding:7px 12px;border:0;background:var(--el-fill-color-light);color:var(--el-text-color-primary);cursor:pointer;text-align:left}.supplement-trigger:hover{background:var(--el-fill-color)}.supplement-trigger:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}.supplement-trigger__title{font-size:14px;font-weight:600}.supplement-trigger__status{margin-left:8px;padding:1px 7px;border-radius:10px;background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-size:12px}.supplement-trigger__hint{margin-left:auto;color:var(--el-text-color-secondary);font-size:12px}.supplement-trigger__arrow{margin-left:6px;transition:transform .2s}.supplement-trigger__arrow.is-expanded{transform:rotate(180deg)}.supplement-form{padding:10px 12px 12px}.supplement-form :deep(.el-form-item){margin-bottom:0}.mail-meta{margin:14px 0}.recipient-tag{margin:2px 6px 2px 0}.mail-form{margin-top:14px}.mail-preview-content{min-height:300px}.readonly-note{width:100%;padding:10px 12px;border:1px solid var(--el-border-color);border-radius:6px;background:#f1f5f9;color:#475569;white-space:pre-wrap;word-break:break-word}:global(.daily-report-dialog){display:flex;max-height:90vh;overflow:hidden;flex-direction:column}:global(.daily-report-dialog .el-dialog__header),:global(.daily-report-dialog .el-dialog__footer){flex:none}:global(.daily-report-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.daily-report-dialog .el-dialog__footer){display:flex;align-items:center;border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}
.mail-signature-preview{width:100%;padding:10px 12px;border:1px solid var(--el-border-color);border-radius:6px;background:#f1f5f9;color:#475569;line-height:1.65;word-break:break-word}.mail-signature-preview :deep(p){margin:0 0 6px}
@media(max-width:768px){.report-toolbar{align-items:flex-start;flex-direction:column}.toolbar-primary{width:100%}.toolbar-actions{width:100%;justify-content:flex-start}.mail-meta{--el-descriptions-table-border:var(--el-border-color-lighter)}}
</style>

<style scoped>.report-feedback-section{margin-top:20px;padding:16px;border:1px solid #dbe3ec;border-radius:8px}</style>

<style scoped>.report-autosave-state{font-size:12px;color:#64748b;margin:8px 0}</style>
