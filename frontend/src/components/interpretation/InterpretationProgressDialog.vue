<template>
 <DraggableFormDialog v-model="visible" title="口译项目进度" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body class="interpretation-three-progress" :close-on-click-modal="false">
  <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="口译项目进度" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"/></template>
  <div ref="body" v-loading="loading"><ChatOrderIdentity :title="project?.projectName||''" :order-no="project?.orderNo||''" project-type="interpretation"/>
   <AppForm ref="formRef" :model="form" label-position="top">
    <el-form-item label="进度类型"><el-select v-model="track" @change="loadHistory"><el-option v-for="(label,key) in labels" :key="key" :label="label" :value="key"/></el-select></el-form-item>
    <el-form-item v-if="track==='project'" label="项目状态" prop="projectStatus" :rules="[{required:true,message:'请选择项目状态'}]"><el-select v-model="form.projectStatus" @change="selectStatus"><el-option v-for="option in statuses" :key="option.value" :value="option.value" :label="option.label"/></el-select></el-form-item>
    <el-form-item label="节点时间（UTC+8）" prop="effectiveOn" :rules="[{required:true,message:'请选择节点时间'}]"><el-date-picker v-model="form.effectiveOn" type="datetime" value-format="YYYY-MM-DD HH:mm:ss"/></el-form-item>
    <el-form-item :label="track==='project'?'进度/说明':labels[track]" prop="changeNote" :rules="[{required:true,whitespace:true,message:'请填写具体进度'}]"><ScreenshotInput v-model="form.changeNote" type="textarea" :rows="4" maxlength="9500" @uploading-change="uploading=$event"/></el-form-item>
    <el-form-item label="是否发送到会话"><el-radio-group v-model="sendToChat"><el-radio :value="true">保存并发送到会话</el-radio><el-radio :value="false">只保存进度</el-radio></el-radio-group></el-form-item>
    <el-form-item v-if="sendToChat" label="@ 人员"><el-select v-model="userIds" multiple><el-option v-for="person in users" :key="person.id" :value="person.id" :label="person.name"/></el-select><small>默认 @ 该项目客户经理、项目经理中的其他人，排除本人。</small></el-form-item>
   </AppForm><el-alert v-if="error" :title="error" type="error" :closable="false"/>
   <h4>{{labels[track]}}记录 <el-button link @click="loadHistory">刷新</el-button></h4><el-timeline><el-timeline-item v-for="row in history" :key="row.id" :timestamp="formatBusinessDateTime(row.effectiveOn)"><b v-if="track==='project'">{{statuses.find(item=>item.value===row.toStatus)?.label||row.toStatus}}</b><ScreenshotText :text="row.changeNote"/><small>{{row.changedByName}}</small></el-timeline-item></el-timeline>
  </div>
  <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||uploading||!project" @click="save">{{sendToChat?'保存并发送到会话':'保存进度'}}</el-button></template>
 </DraggableFormDialog><PartialCancellationReasonDialog ref="cancellation"/>
</template>
<script setup>
import {nextTick,ref,reactive} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {getInterpretationProject} from '@/api/interpretationProjects'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import {progressChatDraft} from '@/utils/annotationCustomerProgress'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import ChatOrderIdentity from '@/components/chat/ChatOrderIdentity.vue'
import ScreenshotInput from '@/components/common/ScreenshotInput.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import PartialCancellationReasonDialog from '@/components/common/PartialCancellationReasonDialog.vue'
const emit=defineEmits(['saved']),visible=ref(false),loading=ref(false),saving=ref(false),uploading=ref(false),error=ref(''),project=ref(),track=ref('project'),history=ref([]),users=ref([]),statuses=ref([]),userIds=ref([]),sendToChat=ref(true),formRef=ref(),body=ref(),cancellation=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const labels={project:'项目进度',customer:'客户进度',interpreter:'译员情况'},form=reactive({projectStatus:'',effectiveOn:'',changeNote:''})
let id='',previousStatus='',cancellationDetails=null,requestKey='',version=0
async function open(projectId,message=null,type='project',excerpt=''){id=String(projectId);const current=++version;visible.value=true;loading.value=true;project.value=null;error.value='';track.value=type==='annotator'?'interpreter':type;clearFieldSearch();requestKey=crypto.randomUUID();sendToChat.value=true;cancellationDetails=null
 try{const [item,context]=await Promise.all([getInterpretationProject(id),api.get(`/projects/interpretation/${id}/progress-context`)]);if(current!==version)return;project.value=item;users.value=context.users;statuses.value=context.statuses;userIds.value=users.value.map(person=>person.id);previousStatus=item.projectStatus;const draft=message?progressChatDraft([{...message,content:excerpt||message.content}]):{effectiveOn:businessDateTimeInputValue(),changeNote:''};Object.assign(form,{projectStatus:item.projectStatus,...draft});await nextTick();formRef.value?.clearValidate();await loadHistory()}catch(e){error.value=e.detail||e.message||'进度加载失败'}finally{if(current===version)loading.value=false}}
let historyVersion=0
async function loadHistory(){if(!id)return;const current=++historyVersion;try{const rows=await api.get(`/projects/interpretation/${id}/progress-records`,{params:{track:track.value}});if(current===historyVersion)history.value=rows}catch(e){error.value=e.detail||'进度记录加载失败'}}
async function selectStatus(status){if(['cancelled','partially_cancelled'].includes(status)&&status!==project.value.projectStatus){const note=await cancellation.value.open(form.changeNote,{status,interpreters:project.value.interpreterAssignments||[],details:cancellationDetails});if(note==null){form.projectStatus=previousStatus;return}form.changeNote=note;cancellationDetails=cancellation.value.getDetails()}else cancellationDetails=null;previousStatus=form.projectStatus}
async function save(){if(saving.value||!await formRef.value.validate().catch(()=>false))return;saving.value=true;try{await api.post(`/projects/interpretation/${id}/progress-records`,{track:track.value,project_status:form.projectStatus,effective_on:form.effectiveOn.replace(' ','T')+'+08:00',change_note:form.changeNote,expected_updated_at:project.value.updatedAt,cancellation_details:track.value==='project'?cancellationDetails:null,request_key:requestKey,send_to_chat:sendToChat.value,user_ids:userIds.value});visible.value=false;ElMessage.success('进度已保存');emit('saved');window.dispatchEvent(new CustomEvent('interpretation-progress-saved',{detail:{projectId:id,track:track.value}}))}catch(e){error.value=e.detail||e.message||'保存失败'}finally{saving.value=false}}
defineExpose({open})
</script>
<style scoped>.el-select{width:100%}small{font-size:12px;color:var(--el-text-color-secondary);display:block;margin-top:6px}</style>
