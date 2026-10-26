<template>
  <DraggableFormDialog v-model="visible" :title="'添加'+trackLabel" width="min(760px, calc(100vw - 32px))" top="6vh" class="issue-dialog" append-to-body :z-index="100004" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
    <div v-loading="loading"><ChatOrderIdentity :title="project?.projectName||''" :order-no="project?.orderNo||''" project-type="annotation" />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="进度类型"><div class="chat-progress-tools"><AnnotationProgressTrackSelect :model-value="track" :disabled="loading||saving" @change="switchTrack" /><el-button :disabled="loading||saving||!project" @click="openHistory">查看具体进度</el-button></div></el-form-item>
        <el-form-item v-if="track==='project'" label="所属状态" prop="projectStatus"><ReadonlyField :model-value="annotationStatusLabel(form.projectStatus)" source="auto" /></el-form-item>
        <el-form-item label="节点时间（UTC+8）" prop="effectiveOn"><el-date-picker v-model="form.effectiveOn" popper-class="annotation-progress-entry-date-popper" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm:ss" /></el-form-item>
        <el-form-item :label="trackLabel" prop="changeNote"><el-input v-model="form.changeNote" type="textarea" :autosize="{minRows:5,maxRows:12}" maxlength="10000" show-word-limit /></el-form-item>
        <AnnotationProgressDeliveryFields v-if="visible" v-model="delivery" :project-id="targetId" :project="project" :disabled="saving" @state="deliveryState=$event" />
      </AppForm>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||!project||deliveryState.loading||(delivery.sendToChat&&!!deliveryState.error)" @click="save">{{ delivery.sendToChat?'保存并发送到会话':'保存'+trackLabel }}</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="historyVisible" :title="historyLabel+'记录'" width="min(850px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body :z-index="100005">
    <ChatOrderIdentity :title="project?.projectName||''" :order-no="project?.orderNo||''" project-type="annotation" />
    <div class="chat-progress-tools"><AnnotationProgressTrackSelect :model-value="historyTrack" @change="changeHistoryTrack" /><el-button :loading="historyLoading" @click="loadHistory">刷新</el-button></div>
    <div v-loading="historyLoading">
      <el-alert v-if="historyError" :title="historyError" type="error" :closable="false" />
      <el-timeline v-else><el-timeline-item v-for="row in historyRows" :key="row.id" :timestamp="formatBusinessDateTime(row.effectiveOn || row.changedAt)" placement="top"><b v-if="historyTrack==='project'">{{ annotationStatusLabel(row.toStatus) }}</b><ScreenshotText :text="row.changeNote || '暂无具体进度'" /><p class="chat-progress-meta">{{ row.changedByName || '系统' }}</p></el-timeline-item></el-timeline>
      <el-empty v-if="!historyLoading&&!historyError&&!historyRows.length" :description="'暂无'+historyLabel+'记录'" :image-size="48" />
    </div>
    <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed,nextTick,onBeforeUnmount,reactive,ref,watch } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import ChatOrderIdentity from './ChatOrderIdentity.vue'
import { getAnnotationProject } from '@/api/annotationProjects'
import { saveAnnotationChatProgress } from '@/api/annotationChatProgress'
import { progressChatDraft } from '@/utils/annotationCustomerProgress'
import { annotationStatusLabel } from '@/utils/annotationStatus'
import AnnotationProgressDeliveryFields from './AnnotationProgressDeliveryFields.vue'
import AnnotationProgressTrackSelect from '@/components/annotation/AnnotationProgressTrackSelect.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { getStatusHistory,getCustomerProgress,getAnnotatorProgress } from '@/api/annotationOps'
import { formatBusinessDateTime } from '@/utils/dateTime'
import '@/views/resource/components/issueDialogs.css'
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),track=ref('project'),project=ref(null),formRef=ref()
const trackLabel=computed(()=>({project:'项目进度',customer:'客户进度',annotator:'标注员情况'}[track.value]))
const form=reactive({projectStatus:'',effectiveOn:'',changeNote:''})
const delivery=ref({sendToChat:true,userIds:[],departmentIds:[]}),deliveryState=ref({loading:false,error:''})
const rules={projectStatus:[{required:true,message:'请先在项目管理中设置项目状态',trigger:'change'}],effectiveOn:[{required:true,message:'请选择节点时间',trigger:'change'}],changeNote:[{required:true,whitespace:true,message:'请填写具体进度',trigger:'blur'}]}
let targetId='',version=0
const drafts={}
const historyVisible=ref(false),historyTrack=ref('project'),historyRows=ref([]),historyLoading=ref(false),historyError=ref('')
const historyLabel=computed(()=>({project:'项目进度',customer:'客户进度',annotator:'标注员情况'}[historyTrack.value]))
let historyController,historyVersion=0
async function switchTrack(value){
  if(loading.value||saving.value||!['project','customer','annotator'].includes(value))return
  drafts[track.value]={...form};track.value=value;Object.assign(form,drafts[value]);error.value=''
  await nextTick();formRef.value?.clearValidate()
}
function openHistory(){historyTrack.value=track.value;historyVisible.value=true;void loadHistory()}
function changeHistoryTrack(value){historyTrack.value=value;void loadHistory()}
async function loadHistory(){
  historyController?.abort();historyController=new AbortController();const current=++historyVersion
  historyLoading.value=true;historyError.value='';historyRows.value=[]
  try{const loader={project:getStatusHistory,customer:getCustomerProgress,annotator:getAnnotatorProgress}[historyTrack.value];const rows=await loader(targetId,{signal:historyController.signal});if(current===historyVersion)historyRows.value=Array.isArray(rows)?rows:[]}
  catch(e){if(current===historyVersion&&e.code!=='ERR_CANCELED')historyError.value=e.detail||e.message||'进度记录加载失败'}
  finally{if(current===historyVersion)historyLoading.value=false}
}
watch(historyVisible,value=>{if(!value){historyController?.abort();++historyVersion;historyLoading.value=false}})
watch(visible,value=>{if(!value)historyVisible.value=false})
onBeforeUnmount(()=>{historyController?.abort();++historyVersion})
async function open(projectId,message,type,excerpt=''){
  if(saving.value)return
  const current=++version;targetId=String(projectId);track.value=type;delivery.value={sendToChat:true,userIds:[],departmentIds:[]};deliveryState.value={loading:false,error:''};visible.value=true;loading.value=true;error.value='';project.value=null;historyVisible.value=false
  try{const draft=progressChatDraft([{...message,content:excerpt||message.content}]);const data=await getAnnotationProject(targetId);if(current!==version)return;project.value=data;const initial={projectStatus:data.projectStatus||'',effectiveOn:draft.effectiveOn,changeNote:draft.changeNote};for(const key of ['project','customer','annotator'])drafts[key]={...initial};Object.assign(form,initial);await nextTick();formRef.value?.clearValidate()}
  catch(e){if(current===version)error.value=e.detail||e.message||'项目加载失败'}finally{if(current===version)loading.value=false}
}
async function save(){
  if(saving.value||loading.value||deliveryState.value.loading||(delivery.value.sendToChat&&deliveryState.value.error)||!await formRef.value.validate().catch(()=>false))return
  saving.value=true;error.value=''
  try{const chatDelivery={...delivery.value};await saveAnnotationChatProgress({projectId:targetId,track:track.value,...form,chatDelivery});window.dispatchEvent(new CustomEvent('annotation-chat-progress-saved',{detail:{projectId:targetId,track:track.value}}));visible.value=false;ElMessage.success('已保存到该订单的'+trackLabel.value)}
  catch(e){error.value=e.detail||e.message||'进度保存失败'}finally{saving.value=false}
}
defineExpose({open})
</script>
<style scoped>.chat-progress-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:10px 0}.chat-progress-meta{font-size:12px;color:#64748b}</style>
