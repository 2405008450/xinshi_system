<template>
  <div class="daily-report-panel" data-auto-draft="off">
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
        </div>
        <span v-if="editable" class="sheet-tip">
          <el-icon class="sheet-tip__icon"><InfoFilled /></el-icon>
          直接填写单元格，Tab 切换；重复订单归入二级，系统记录为灰底只读。报告归属所选日期，保存与提交时间另行记录。
        </span>
      </div>
      <div class="toolbar-actions">
        <el-button v-if="editable&&!amending" size="small" :loading="loading" @click="loadReport(true)">重新汇总</el-button>
        <el-button v-if="editable" size="small" @click="sheetRef?.add()">新增一行</el-button>
        <Teleport :to="footerTarget || 'body'" :disabled="!footerTarget">
          <el-button v-if="editable&&!amending" size="small" type="primary" plain :loading="saving || validating" @click="save(false)">保存草稿</el-button>
          <el-button v-if="editable" size="small" type="success" :loading="saving || validating" @click="save(true)">{{amending?'保存一次修订':'确认报告'}}</el-button>
        </Teleport>
        <el-button v-if="report.can_amend&&!amending" size="small" type="warning" plain @click="amending=true">修改一次</el-button><el-button v-if="amending" size="small" :disabled="saving" @click="loadReport(false)">取消修订</el-button>
        <el-button size="small" :disabled="report.status !== 'finalized'" :loading="exporting" @click="downloadReport">导出 Excel</el-button>
      </div>
    </div>

    <div class="report-autosave-state" role="status">{{autosaveLabel}}</div><el-alert v-if="localDraftError||reportCloud.error" :title="localDraftError||reportCloud.error" type="warning" :closable="false" />
    <el-alert v-if="submitNotice" :title="submitNotice" :type="submitNoticeType" show-icon :closable="false" class="report-submit-notice" />
    <ReportDailyNotices :idle-minutes="report.idle_minutes" :has-lunch-work="hasLunchWork" />
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

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DailyReportEditor from './DailyReportEditor.vue'
import ReportIdleTime from './ReportIdleTime.vue'
import ReportDailyNotices from './ReportDailyNotices.vue'
import ReportFeedbackPanel from './ReportFeedbackPanel.vue'
import ReportRevisionHistory from './ReportRevisionHistory.vue'
import {subscribe} from '@/utils/realtimeSocket'
import {readCloudDraft,queueCloudDraft,saveCloudDraft,cloudDraftStatus,cloudDraftRevision,acknowledgeCloudDraft} from '@/utils/cloudDrafts'
import {chooseDraft} from '@/utils/draftRecovery'
import {createAutoDraftStore} from '@/utils/autoDraftStore'
import {mergeAnnotationOperationRows,newReportRow,reportBusinessDate,reportWeekday,shiftReportDate,requiresProjectIdentity,updateRowTypes} from '@/utils/workReportForm'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { projectTypeNames } from '@/utils/projectIdentity'
import {
  getDailyReportEditorContext,
  amendDailyReport,
  exportDailyReport,
  finalizeDailyReport,
  previewDailyReport,
} from '@/api/tasks'


const props = defineProps({ reportDate: { type: String, required: true }, initialFieldWork: Object, footerTarget: Object, annotationProject: Object })
const emit = defineEmits(['status-change','update:report-date','annotation-project-applied'])
const loading = ref(false)
const saving = ref(false)
const validating = ref(false)
const submitNotice = ref('')
const submitNoticeType = ref('warning')
const exporting = ref(false)
const dirtyCount = ref(0)
const supplementDirty = ref(false)
const supplementExpanded = ref(false)
const sheetRef = ref(null)
const hasLunchWork = ref(false)
const localDraftError=ref('')
const reportCloud=computed(()=>cloudDraftStatus('work-report',props.reportDate))
const autosaveLabel=computed(()=>localDraftError.value||reportCloud.value.error?'自动保存异常，请查看下方提示':reportCloud.value.state==='synced'?'草稿已同步云端':reportCloud.value.state==='saving'?'正在同步云端…':hasUnsavedChanges.value?'已在本机备份，等待同步云端':'自动保存已开启：本机即时备份，云端约3秒')
const idleTimeRef=ref()
const report = reactive({idle_minutes:null,idle_declaration_confirmed:false,idle_declaration_text:null, can_amend:false,amendment_used:false,user_name: '', id: null, status: 'draft', supplemental_note: '', items: [] })
watch(() => report.items, items => { hasLunchWork.value = items.some(item => item.display_metadata?.lunch_overtime === true) }, { flush: 'sync' })


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
      report.items=Array.isArray(draft.items)?mergeAnnotationOperationRows(draft.items,report.items):report.items
      report.supplemental_note=draft.supplemental_note||''
      report.idle_minutes=draft.idle_minutes??null
      report.idle_declaration_confirmed=draft.idle_declaration_confirmed===true
      await nextTick();dirtyCount.value=1
      if(draft===local&&cloud)cacheDraft(date,true)
    }
    if (sequence === loadSequence) await applyFieldWork(date)
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
let fieldWorkApplied = false
async function applyFieldWork(date) {
  const record = props.initialFieldWork
  if (!record || fieldWorkApplied || date !== reportBusinessDate(record.start_at)) return
  if (report.status === 'finalized' && !amending.value) {
    ElMessage.warning('该日工作报告已确认，请先点击「修改一次」开启修订')
    return
  }
  fieldWorkApplied = true
  const index = report.items.findIndex(row => row.display_metadata?.field_work_id === record.id)
  if (index >= 0) {
    await nextTick()
    sheetRef.value?.focusReportRow(index)
    return
  }
  const typePath = record.type_path
  const category = typePath[1] === 'bidding'
    ? (typePath[2] === 'accompany' ? '陪标' : '投标')
    : record.type_label.split(' / ').at(-1)
  const duration = Math.round((Date.parse(record.end_at) - Date.parse(record.start_at)) / 60000)
  const content = [
    record.type_label, record.client_name, `地点：${record.location}`,
    `${formatBusinessDateTimeMinute(record.start_at)} 至 ${formatBusinessDateTimeMinute(record.end_at)}`,
    record.companion_names ? `陪同人：${record.companion_names}` : '',
    record.notes,
  ].filter(Boolean).join('\n')
  report.items = [...report.items, {
    source_type: 'manual', source_id: record.id, task_type: '外勤工作',
    task_name: record.client_name || record.type_label,
    progress_content: content, duration_minutes: duration > 0 && duration <= 1440 ? duration : 0,
    display_metadata: { report_types: [`外勤工作::${category}`], field_work_id: record.id, _feedback_key: record.id },
  }]
  await nextTick()
  dirtyCount.value = 1
  cacheDraft(date)
  sheetRef.value?.focusReportRow(report.items.length - 1)
}
watch(amending, value => { if (value && !loading.value) void applyFieldWork(props.reportDate) })

let handledAnnotationProject
let warnedAnnotationProject
watch([() => props.annotationProject, () => props.reportDate, loadedDate, loading, saving, amending], async () => {
  const project = props.annotationProject
  if (!project || handledAnnotationProject === project || loading.value || saving.value ||
    loadedDate.value !== props.reportDate || props.reportDate !== reportBusinessDate() || !sheetRef.value) return
  if (!editable.value) {
    if (warnedAnnotationProject !== project) {
      warnedAnnotationProject = project
      ElMessage.warning(report.can_amend ? '当前工作报告已确认，请点击「修改一次」后填写' : '当前工作报告已确认，无法新增工作记录')
    }
    if (!report.can_amend) emit('annotation-project-applied', project.id)
    return
  }
  handledAnnotationProject = project
  const rows = sheetRef.value.getRows()
  const type = project.type || 'annotation'
  const category = projectTypeNames[type]
  let index = rows.findIndex(row => row.source_type === 'manual' &&
    (row.display_metadata?.project_id === project.id || type === 'annotation' && row.display_metadata?.chat_annotation_project_id === project.id) &&
    row.display_metadata.report_types?.includes(category) && !row.progress_content?.trim())
  if (index === -1) {
    const row = newReportRow()
    updateRowTypes(row, [category])
    index = rows.length
    rows.push(row)
  }
  const row = rows[index]
  if (!row.task_name?.trim()) row.task_name = Array.from(project.name).slice(0, 255).join('')
  Object.assign(row.display_metadata, { project_id: project.id, selected_project_type: category, selected_project_name: project.name, order_no: project.orderNo || row.display_metadata.order_no || '' })
  if (type === 'annotation') row.display_metadata.chat_annotation_project_id = project.id
  report.items = rows
  await nextTick()
  onEditorChange(Math.max(1, dirtyCount.value))
  emit('annotation-project-applied', project.id)
  await sheetRef.value?.focusReportRow(index, 'textarea[aria-label$="具体任务"]')
}, { flush: 'post' })

function cacheDraft(date=props.reportDate,force=false){
 if((report.status==='finalized'&&!amending.value)||loadedDate.value!==date||(!force&&!hasUnsavedChanges.value))return
 const value=autoDraftPayload(date)
 let snapshot={...value,_savedAt:Date.now(),_baseRevision:cloudDraftRevision('work-report',date)}
 try{
  const previous=JSON.parse(localStorage.getItem(draftKey(date))||'null')
  if(previous&&JSON.stringify({...previous,_savedAt:undefined,_baseRevision:undefined})===JSON.stringify(value))snapshot=previous
  else localStorage.setItem(draftKey(date),JSON.stringify(snapshot))
  localDraftError.value=''
 }catch{localDraftError.value='浏览器备份失败，请检查存储空间；正在尝试同步云端'}
 queueCloudDraft('work-report',date,snapshot)
 return snapshot
}
function onIdleChange(){submitNotice.value='';supplementDirty.value=true;cacheDraft()}
function onEditorChange(count){
  submitNotice.value=''
  dirtyCount.value=count
  // el-input 的 input 事件早于 update:modelValue，等待该轮赋值后再备份。
  nextTick(()=>{
    hasLunchWork.value=(sheetRef.value?.getRows()||report.items).some(item=>item.display_metadata?.lunch_overtime===true)
    cacheDraft()
  })
}
function changeDate(date){if(!date||date===props.reportDate)return;cacheDraft();emit('update:report-date',date)}
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
  if (!finalize) return saveEditDraft()
  if (saving.value || validating.value) return
  if (loading.value || !editable.value) {
    submissionNotice('当前报告尚未加载完成或已确认，请等待加载完成后再操作')
    return
  }
  const date = props.reportDate
  const amendment = amending.value
  validating.value = true
  submitNotice.value = ''
  cacheDraft(date,true)
  try {
    try {
      if (!idleTimeRef.value || !await idleTimeRef.value.validate()) {
        throw new Error('请填写空闲时间并确认声明')
      }
    } catch {
      submissionNotice('尚未提交：请填写空闲时间并确认声明')
      return
    }
    try {
      if (!sheetRef.value || !await sheetRef.value.validate()) {
        throw new Error('请检查工作报告必填内容')
      }
    } catch (error) {
      const firstField = error && !(error instanceof Error)
        ? Object.entries(error).find(([, issues]) => Array.isArray(issues) && issues.length)
        : null
      const index = firstField?.[0].match(/^rows\.(\d+)\./)?.[1]
      const detail = firstField?.[1]?.[0]?.message
      const message = detail
        ? `${index === undefined ? '' : '第' + (Number(index) + 1) + '行：'}${detail}`
        : getLocalizedErrorMessage(error, '请补全任务类型、具体任务、工作量、单位和耗时')
      submissionNotice('尚未提交：' + message)
      return
    }
    if (date !== props.reportDate) {
      submissionNotice('报告日期已变化，请核对当前日期后重新提交')
      return
    }
    const payload = reportPayload()
    if (payload.items.some(item => !item.task_type?.trim() || (requiresProjectIdentity(item)&&!item.task_name?.trim()) || !item.progress_content?.trim())) {
      submissionNotice('尚未提交：请补全任务类型、具体任务及必填的项目名称')
      return
    }
    if (finalize) await ElMessageBox.confirm(`报告日期：${date}。`+(amending.value?'保存后将更新已提交的工作报告，并用完本日报告的一次修改机会，修改记录对查看人可见。是否保存？':'确认后将保存并发送该日期的工作报告，接收人可在系统「查看工作报告」中查看。确认后仅有一次修订机会，是否继续？'), '确认报告', { type: 'warning' })
    if (date !== props.reportDate) {
      submissionNotice('报告日期已变化，请核对当前日期后重新提交')
      return
    }
    saving.value = true
    const data=await (amending.value?amendDailyReport:finalizeDailyReport)(date, payload)
    if (!data?.id || data.report_date !== date || data.status !== (finalize || amendment ? 'finalized' : 'draft')) {
      throw new Error('未收到正确的保存结果，请刷新报告核对提交状态')
    }
    try{localStorage.removeItem(draftKey(date))}catch{/* 不影响数据库保存结果。 */}
    acknowledgeCloudDraft('work-report',date,data.edit_draft_revision||0)
    if(date===props.reportDate)applyReport(data)
    if(data.status==='finalized')window.dispatchEvent(new Event('work-report-lunch-changed'))
    submissionNotice(amendment ? '工作报告修订已保存，接收人可查看更新后的报告'
      : finalize ? `工作报告已保存并发送，报告日期：${date}，可在系统「查看工作报告」中查看` : '草稿已保存', 'success')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      submissionNotice('保存或提交未完成：' + getLocalizedErrorMessage(error, '请求失败，请稍后重试'), 'error')
    }
  } finally { saving.value = false; validating.value = false }
}

async function saveEditDraft() {
  if(saving.value||validating.value||loading.value||!editable.value)return
  const date=props.reportDate
  saving.value=true
  submitNotice.value=''
  try{
    const snapshot=cacheDraft(date,true)
    if(!snapshot)throw new Error('当前日期的报告尚未准备好，请稍后重试')
    await saveCloudDraft('work-report',date,snapshot)
    submissionNotice(`草稿已保存，报告日期：${date}，未填写完整的内容也已保留，刷新后可继续填写`,'success')
  }catch(error){
    submissionNotice('云端草稿保存未完成：'+getLocalizedErrorMessage(error,'请稍后重试')+
      (localDraftError.value?'；'+localDraftError.value:'；本机已备份当前内容'),'error')
  }finally{saving.value=false}
}

function submissionNotice(message, type = 'warning') {
  submitNotice.value = message
  submitNoticeType.value = type
  ElMessage({ message, type })
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

function onReportHidden(){if(document.hidden)cacheDraft()}
function refreshAnnotationOperations(){if(saving.value||props.reportDate!==reportBusinessDate())return;cacheDraft();loadReport(false)}
function beforeUnload() {
  if (!hasUnsavedChanges.value) return
  cacheDraft()
}

watch(() => props.reportDate, async (_date,previousDate) => {
  submitNotice.value = ''
  cacheDraft(previousDate)
  supplementExpanded.value = false
  await loadReport(false)
})
const stopUpdates=subscribe('daily_report_updated',event=>{if(event.user_id!==owner||event.report_date!==props.reportDate)return;if(hasUnsavedChanges.value)ElMessage.info('新咨询工作项已追加，保存当前修改时会自动保留');else loadReport(false)})
onMounted(() => { loadReport(false); loadEditorContext(); window.addEventListener('annotation-operation-report-added',refreshAnnotationOperations);window.addEventListener('open-my-work-report',refreshAnnotationOperations);window.addEventListener('beforeunload', beforeUnload);document.addEventListener('visibilitychange',onReportHidden) })
onBeforeUnmount(() => {stopUpdates();cacheDraft();loadSequence++;loadController?.abort();window.removeEventListener('annotation-operation-report-added',refreshAnnotationOperations);window.removeEventListener('open-my-work-report',refreshAnnotationOperations);window.removeEventListener('beforeunload', beforeUnload);document.removeEventListener('visibilitychange',onReportHidden)})
defineExpose({prepareClose(){if(saving.value||validating.value)return false;cacheDraft();return !localDraftError.value}})
</script>

<style scoped>
.report-identity{display:flex;flex-wrap:wrap;gap:14px 24px;align-items:center;padding:12px 0 16px}.report-date{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.report-date :deep(.el-date-editor){width:150px}.report-departments{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.daily-report-panel{min-width:0}.report-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}.toolbar-primary{display:flex;align-items:center;gap:10px;flex:1;min-width:0;flex-wrap:wrap}.toolbar-status,.toolbar-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.toolbar-actions{justify-content:flex-end;flex-shrink:0}.sheet-tip{display:inline-flex;align-items:center;gap:4px;font-size:12px;line-height:1.4;color:var(--el-color-info)}.sheet-tip__icon{flex-shrink:0;font-size:14px}.supplement-section{margin-top:8px;border:1px solid var(--el-border-color-lighter);border-radius:6px;background:var(--el-bg-color);overflow:hidden}.supplement-trigger{display:flex;align-items:center;width:100%;min-height:38px;padding:7px 12px;border:0;background:var(--el-fill-color-light);color:var(--el-text-color-primary);cursor:pointer;text-align:left}.supplement-trigger:hover{background:var(--el-fill-color)}.supplement-trigger:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}.supplement-trigger__title{font-size:14px;font-weight:600}.supplement-trigger__status{margin-left:8px;padding:1px 7px;border-radius:10px;background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-size:12px}.supplement-trigger__hint{margin-left:auto;color:var(--el-text-color-secondary);font-size:12px}.supplement-trigger__arrow{margin-left:6px;transition:transform .2s}.supplement-trigger__arrow.is-expanded{transform:rotate(180deg)}.supplement-form{padding:10px 12px 12px}.supplement-form :deep(.el-form-item){margin-bottom:0}
@media(max-width:768px){.report-toolbar{align-items:flex-start;flex-direction:column}.toolbar-primary{width:100%}.toolbar-actions{width:100%;justify-content:flex-start}}
</style>

<style scoped>.report-feedback-section{margin-top:20px;padding:16px;border:1px solid #dbe3ec;border-radius:8px}</style>

<style scoped>.report-autosave-state{font-size:12px;color:#64748b;margin:8px 0}</style>
