<template>
  <DraggableFormDialog :model-value="modelValue" width="min(980px, calc(100vw - 32px))" top="5vh" class="translation-unified-progress" :before-close="beforeClose" @update:model-value="value=>emit('update:modelValue',value)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`项目进度 · ${project?.orderNo || ''}`" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <p>{{ project?.projectName || project?.sourceFileName || '笔译项目' }}</p>
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <ProjectProgressEntryForm v-if="canWrite" ref="entryRef" :show-submit="false" :model-value="form" :statuses="statuses" :disabled="loading || !!error" :saving="saving" @update:model-value="value=>Object.assign(form,value)" @submit="save" />
      <el-divider content-position="left">项目进度记录</el-divider>
      <el-timeline><el-timeline-item v-for="item in records" :key="item.id" :timestamp="formatBusinessDateTimeMinute(item.effective_on)" placement="top"><b>{{ label(item.to_status) }}</b><span v-if="item.from_status!==item.to_status">（由{{ label(item.from_status) }}变更）</span><p class="translation-progress-note"><ScreenshotText :text="item.change_note" /></p><small>{{ item.changed_by_name }}</small></el-timeline-item></el-timeline>
      <el-empty v-if="!loading && !records.length" description="暂无项目进度记录" />
    </div>
    <template #footer><el-button :disabled="saving" @click="emit('update:modelValue',false)">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="saving" :disabled="loading || !!error" @click="entryRef?.submit()">保存项目进度</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import ProjectProgressEntryForm from './ProjectProgressEntryForm.vue'
import ScreenshotText from './ScreenshotText.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {useFormDraft} from '@/composables/useFormDraft'
import {businessDateTimeInputValue,formatBusinessDateTimeMinute} from '@/utils/dateTime'
import {getProjectStatusOptions,normalizeProjectStatus} from '@/utils/projectStatus'
import {createRequestUuid} from '@/utils/idempotency'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Boolean,project:Object,canWrite:Boolean})
const emit=defineEmits(['update:modelValue','saved'])
const bodyRef=ref(),{fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(bodyRef)
const statuses=getProjectStatusOptions('translation')
const label=value=>statuses.find(item=>item.value===normalizeProjectStatus('translation',value))?.label||value||'未设置'
const emptyForm=()=>({projectStatus:'',effectiveOn:'',changeNote:'',sourceVersion:null})
const form=reactive(emptyForm())
const {beginDraft,pauseDraft,clearDraft,startFreshDraft}=useFormDraft({namespace:'translation-project-progress',form,createDefault:emptyForm})
const entryRef=ref()
const loading=ref(false),saving=ref(false),error=ref(''),records=ref([]),version=ref(null)
let controller,sequence=0,requestId=''
async function load(){
 const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value=''
 const owner=localStorage.getItem('user_id')
 try{const data=await api.get(`/projects/translation/${props.project.id}/progress`,{signal:controller.signal});if(current!==sequence||owner!==localStorage.getItem('user_id'))return;records.value=data.items;version.value=data.updated_at;form.sourceVersion=data.updated_at;form.projectStatus=normalizeProjectStatus('translation',data.project_status)}
 catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目进度加载失败')}
 finally{if(current===sequence)loading.value=false}
}
async function save(){
 if(saving.value)return;saving.value=true
 try{requestId ||= createRequestUuid();const data=await api.post(`/projects/translation/${props.project.id}/progress`,{project_status:form.projectStatus,change_note:form.changeNote,effective_on:form.effectiveOn.replace(' ','T')+'+08:00',expected_updated_at:form.sourceVersion ?? version.value,request_id:requestId});records.value=data.items;version.value=data.updated_at;form.sourceVersion=data.updated_at;form.projectStatus=normalizeProjectStatus('translation',data.project_status);form.changeNote='';form.effectiveOn=businessDateTimeInputValue().replace(' ','T');requestId='';clearDraft();startFreshDraft(`edit:${props.project.id}`);emit('saved',data);ElMessage.success('项目进度已保存')}
 catch(e){if((e.status||e.response?.status)===409){requestId='';await load()}ElMessage.error(getLocalizedErrorMessage(e,'项目进度保存失败'))}
 finally{saving.value=false}
}
function beforeClose(done){if(!saving.value)done()}
watch(()=>[props.modelValue,props.project?.id],async([open])=>{pauseDraft();if(open){Object.assign(form,emptyForm(),{projectStatus:normalizeProjectStatus('translation',props.project?.projectStatus),effectiveOn:businessDateTimeInputValue().replace(' ','T')});requestId='';records.value=[];const projectId=props.project?.id;await load();if(props.modelValue&&props.project?.id===projectId&&!error.value)await beginDraft(`edit:${projectId}`)}else{sequence++;controller?.abort();clearFieldSearch()}},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style>
.translation-unified-progress{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.translation-unified-progress>.el-dialog__header,.translation-unified-progress>.el-dialog__footer{flex:none}.translation-unified-progress>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.translation-progress-note{white-space:pre-wrap;overflow-wrap:anywhere}
</style>
