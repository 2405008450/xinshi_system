<template>
  <el-button :disabled="!projectId || disabled" :title="projectId ? '添加简单需求、发送通知并查看收到回复' : '请先保存项目，再添加简单需求'" @click="visible=true">简单需求</el-button>
  <DraggableFormDialog v-model="visible" class="simple-requirement-dialog" title="简单需求" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="done=>{if(!saving)done()}" @open="open">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="简单需求" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBody">
    <div class="requirement-project-controls"><span>项目原状态：<el-tag>{{ status(currentStatus) }}</el-tag></span><el-dropdown v-if="canWrite" trigger="click" max-height="min(360px, calc(100vh - 160px))" :disabled="saving||loading" @command="changeStatus"><el-button :disabled="saving||loading">调整项目状态 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="option in statuses" :key="option.value" :command="option.value" :disabled="option.value===normalizeProjectStatus('translation',currentStatus)">{{option.label}}</el-dropdown-item></el-dropdown-menu></template></el-dropdown><el-button v-if="canWrite" type="primary" :disabled="saving||loading" @click="dispatchPanel?.openCompose()">项目经理安排</el-button></div>
    <div class="requirement-deadline" data-dialog-field-search-label="客户回稿时间"><span>客户回稿时间</span><el-date-picker v-if="canWrite" v-model="deadlineDraft" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="请选择客户回稿时间" :disabled="saving||loading" @change="deadlineDirty=true" /><ReadonlyField v-else :model-value="formatBusinessDateTime(customerDeadlineTime)" source="auto" /><el-button v-if="canWrite" :loading="saving" :disabled="loading" @click="saveDeadline">保存回稿时间</el-button></div>
    <AppForm v-if="canWrite" ref="formRef" :model="form" :rules="rules" label-position="top" class="requirement-editor" data-screenshot-editor="own">
      <div class="requirement-editor-columns">
        <el-form-item label="原文" prop="original_text"><el-input v-model="form.original_text" type="textarea" :rows="3" maxlength="2000" show-word-limit :disabled="saving" /></el-form-item>
        <el-form-item label="译文" prop="translated_text"><el-input v-model="form.translated_text" type="textarea" :rows="3" maxlength="2000" show-word-limit :disabled="saving" /></el-form-item>
      </div>
      <div class="requirement-editor-options">
        <el-form-item label="是否收费" prop="chargeable"><el-radio-group v-model="form.chargeable" :disabled="saving"><el-radio :value="true">收费</el-radio><el-radio :value="false">不收费</el-radio></el-radio-group></el-form-item>
        <el-form-item label="发送通知人（笔译项目部，可多选）" prop="recipient_ids"><el-select v-model="form.recipient_ids" multiple filterable :disabled="saving || loading" placeholder="请选择通知人"><el-option v-for="person in people" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
      </div>
      <p class="requirement-tip">保存需求保留当前项目状态并通知所选人员；项目状态可用上方按钮单独调整。</p>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div class="requirement-history-actions"><strong>需求记录及收到回复</strong><el-button text :loading="loading" :disabled="saving" @click="load(page)">刷新回复</el-button></div>
    <div v-loading="loading" class="requirement-history"><el-empty v-if="!items.length && !loading && !error" description="暂无简单需求" :image-size="48" /><TranslationSimpleRequirementRecord v-for="item in items" :key="item.id" :item="item" /></div>
    <el-pagination v-if="total > 10" small layout="prev,pager,next,total" :page-size="10" :total="total" :current-page="page" @current-change="load" />
    <RequirementDispatchPanel ref="dispatchPanel" :active="visible" :blocked="loading||saving" :project-id="projectId" :project-updated-at="projectUpdatedAt" :customer-deadline-time="customerDeadlineTime" :latest-requirement="latestRequirement" :people="people" :can-write="canWrite" />
    <details v-if="legacyTotal" class="legacy-notes"><summary>历史简短记录（{{ legacyTotal }}）</summary><article v-for="item in legacyItems" :key="item.id"><strong>{{ item.actor_name }}</strong> · {{ formatBusinessDateTime(item.created_at) }}<p>{{ item.content }}</p></article><el-pagination v-if="legacyTotal > 10" small layout="prev,pager,next" :page-size="10" :total="legacyTotal" :current-page="legacyPage" @current-change="loadLegacy" /></details>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="saving" :disabled="loading||!!error" @click="save">保存需求</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { formatBusinessDateTime,businessDateTimeInputValue } from '@/utils/dateTime'
import { getProjectStatusLabel,getProjectStatusOptions,normalizeProjectStatus } from '@/utils/projectStatus'
import TranslationSimpleRequirementRecord from '@/components/common/TranslationSimpleRequirementRecord.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import RequirementDispatchPanel from './RequirementDispatchPanel.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
const editorBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
const props = defineProps({ projectId: String, projectUpdatedAt: [String, Date], canWrite: Boolean, disabled: Boolean })
const emit = defineEmits(['saved'])
const visible=ref(false), loading=ref(false), saving=ref(false), error=ref(''), page=ref(1), total=ref(0), items=ref([]), formRef=ref(), currentStatus=ref(), people=ref([])
const legacyItems=ref([]), legacyTotal=ref(0), legacyPage=ref(1)
const statuses=getProjectStatusOptions('translation'),customerDeadlineTime=ref(null),deadlineDraft=ref(''),deadlineDirty=ref(false),latestRequirement=ref(null),dispatchPanel=ref()
const form=reactive({original_text:'',translated_text:'',chargeable:null,recipient_ids:[]})
const rules={original_text:[{validator:(_r,value,done)=>String(value||'').trim()?done():done(new Error('请填写原文')),trigger:'blur'}],chargeable:[{validator:(_r,value,done)=>typeof value==='boolean'?done():done(new Error('请选择收费或不收费')),trigger:'change'}],recipient_ids:[{type:'array',required:true,min:1,message:'请选择通知人',trigger:'change'}]}
const status=value=>getProjectStatusLabel('translation',value)
let sequence=0, controller, attempt, settingsAttempt, defaultsInitialized=false, legacySequence=0
async function open(){clearFieldSearch();await Promise.all([load(1),loadLegacy(1)]);await nextTick();formRef.value?.clearValidate()}
async function load(nextPage){
  if(!props.projectId)return
  const request=++sequence,projectId=props.projectId;controller?.abort();controller=new AbortController();loading.value=true;error.value='';page.value=nextPage
  try{
    const [data,options]=await Promise.all([api.get(`/translation-simple-requirements/projects/${projectId}`,{params:{skip:(nextPage-1)*10,limit:10},signal:controller.signal}),props.canWrite?api.get('/translation-simple-requirements/recipients',{signal:controller.signal}):Promise.resolve({items:[]})])
    if(request!==sequence)return
    items.value=data.items||[];total.value=data.total||0;currentStatus.value=data.project_status;people.value=options.items||[]
    customerDeadlineTime.value=data.customer_deadline_time||null;latestRequirement.value=data.latest_requirement||null
    if(!deadlineDirty.value)deadlineDraft.value=businessDateTimeInputValue(customerDeadlineTime.value)
    if(!defaultsInitialized&&props.canWrite){form.recipient_ids=options.default_recipient_ids||[];defaultsInitialized=true}
  }catch{if(request===sequence)error.value='简单需求加载失败，请关闭后重试'}finally{if(request===sequence)loading.value=false}
}
async function loadLegacy(nextPage){const request=++legacySequence,projectId=props.projectId;if(!projectId)return;try{const data=await api.get(`/projects/translation/${projectId}/short-notes`,{params:{skip:(nextPage-1)*10,limit:10}});if(request===legacySequence&&projectId===props.projectId){legacyItems.value=data.items||[];legacyTotal.value=data.total||0;legacyPage.value=nextPage}}catch{if(request===legacySequence)ElMessage.error('历史简短记录加载失败')}}
async function save(){
  if(saving.value||loading.value||!props.projectId||!props.canWrite||!await formRef.value?.validate().catch(()=>false))return
  if(saving.value)return;saving.value=true
  const projectId=props.projectId,payload={original_text:form.original_text.trim(),translated_text:form.translated_text.trim(),chargeable:form.chargeable,saved_status:normalizeProjectStatus('translation',currentStatus.value)||'simple_requirement',recipient_ids:[...form.recipient_ids],expected_project_status:currentStatus.value??null,expected_updated_at:props.projectUpdatedAt||null},signature=JSON.stringify({projectId,...payload})
  if(attempt?.signature!==signature)attempt={signature,request_id:crypto.randomUUID()}
  try{const data=await api.post(`/translation-simple-requirements/projects/${projectId}`,{...payload,request_id:attempt.request_id});if(projectId!==props.projectId)return;emit('saved',data);form.original_text='';form.translated_text='';form.chargeable=null;attempt=undefined;ElMessage.success('简单需求已保存并发送通知');await load(1);await nextTick();formRef.value?.clearValidate()}catch(error){if(projectId===props.projectId)ElMessage.error(error?.detail||error?.response?.data?.detail||'简单需求保存失败，请重试')}finally{saving.value=false}
}
async function saveSettings(values){
  if(saving.value||loading.value||!props.canWrite||!props.projectId)return
  saving.value=true
  const projectId=props.projectId,payload={...values,expected_updated_at:props.projectUpdatedAt||null},signature=JSON.stringify({projectId,...payload})
  if(settingsAttempt?.signature!==signature)settingsAttempt={signature,request_id:crypto.randomUUID()}
  try{const data=await api.patch(`/translation-simple-requirements/projects/${projectId}/settings`,{...payload,request_id:settingsAttempt.request_id});if(projectId!==props.projectId)return;emit('saved',data);if('customer_deadline_time' in values)deadlineDirty.value=false;settingsAttempt=undefined;await load(page.value);await dispatchPanel.value?.reload();ElMessage.success('项目设置已保存并记录操作历史')}catch(error){ElMessage.error(error?.detail||error?.response?.data?.detail||'保存项目设置失败，请重试')}finally{saving.value=false}
}
const changeStatus=value=>saveSettings({project_status:value})
const saveDeadline=()=>saveSettings({customer_deadline_time:deadlineDraft.value?deadlineDraft.value.replace(' ','T')+'+08:00':null})
watch(()=>props.projectId,()=>{visible.value=false;sequence++;legacySequence++;controller?.abort();items.value=[];total.value=0;legacyItems.value=[];legacyTotal.value=0;Object.assign(form,{original_text:'',translated_text:'',chargeable:null,recipient_ids:[]});error.value='';attempt=undefined;settingsAttempt=undefined;defaultsInitialized=false;loading.value=false;currentStatus.value=undefined;customerDeadlineTime.value=null;deadlineDraft.value='';deadlineDirty.value=false;latestRequirement.value=null})
onBeforeUnmount(()=>{sequence++;legacySequence++;controller?.abort()})
</script>
<style scoped>
.requirement-project-controls,.requirement-deadline{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0}.requirement-deadline :deep(.el-input){max-width:280px}
.requirement-editor{border-bottom:1px solid var(--el-border-color-lighter);padding-bottom:14px}.requirement-editor-columns{display:grid;grid-template-columns:1fr 1fr;gap:16px}.requirement-editor-options{display:grid;grid-template-columns:200px 1fr;gap:16px}.requirement-save-actions{display:flex;gap:10px;flex-wrap:wrap}.requirement-save-actions :deep(.el-button){margin-left:0}.requirement-tip{font-size:12px;color:var(--el-text-color-secondary)}.requirement-history-actions{display:flex;justify-content:space-between;align-items:center;margin-top:10px}.requirement-history{max-height:280px;min-height:50px;overflow:auto}.legacy-notes{margin-top:12px}.legacy-notes article{border-bottom:1px solid var(--el-border-color-lighter);padding:10px 0}.legacy-notes p{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:650px){.requirement-editor-columns,.requirement-editor-options{grid-template-columns:1fr;gap:0}}
</style>
