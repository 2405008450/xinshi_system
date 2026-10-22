<template>
  <DraggableFormDialog v-model="visible" :title="track==='customer'?'添加客户进度':'添加项目进度'" width="min(760px, calc(100vw - 32px))" top="6vh" class="issue-dialog" append-to-body :z-index="100004" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
    <div v-loading="loading"><ChatOrderIdentity :title="project?.projectName||''" :order-no="project?.orderNo||''" project-type="annotation" />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item v-if="track==='project'" label="所属状态" prop="projectStatus"><ReadonlyField :model-value="annotationStatusLabel(form.projectStatus)" source="auto" /></el-form-item>
        <el-form-item label="节点时间（UTC+8）" prop="effectiveOn"><el-date-picker v-model="form.effectiveOn" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm:ss" /></el-form-item>
        <el-form-item :label="track==='customer'?'客户具体进度':'项目具体进度'" prop="changeNote"><el-input v-model="form.changeNote" type="textarea" :autosize="{minRows:5,maxRows:12}" maxlength="10000" show-word-limit /></el-form-item>
      </AppForm>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||!project" @click="save">{{ track==='customer'?'保存客户进度':'保存项目进度' }}</el-button></template>
  </DraggableFormDialog>
  <AnnotationProgressDeliveryDialog ref="deliveryRef" />
</template>
<script setup>
import { reactive,ref } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import ChatOrderIdentity from './ChatOrderIdentity.vue'
import { getAnnotationProject } from '@/api/annotationProjects'
import { saveAnnotationChatProgress } from '@/api/annotationChatProgress'
import { progressChatDraft } from '@/utils/annotationCustomerProgress'
import { annotationStatusLabel } from '@/utils/annotationStatus'
import AnnotationProgressDeliveryDialog from './AnnotationProgressDeliveryDialog.vue'
import '@/views/resource/components/issueDialogs.css'
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),track=ref('project'),project=ref(null),formRef=ref()
const form=reactive({projectStatus:'',effectiveOn:'',changeNote:''})
const deliveryRef=ref()
const rules={projectStatus:[{required:true,message:'请先在项目管理中设置项目状态',trigger:'change'}],effectiveOn:[{required:true,message:'请选择节点时间',trigger:'change'}],changeNote:[{required:true,whitespace:true,message:'请填写具体进度',trigger:'blur'}]}
let targetId='',version=0
async function open(projectId,message,type,excerpt=''){
  if(saving.value)return
  const current=++version;targetId=String(projectId);track.value=type;visible.value=true;loading.value=true;error.value='';project.value=null
  try{const draft=progressChatDraft([{...message,content:excerpt||message.content}]);const data=await getAnnotationProject(targetId);if(current!==version)return;project.value=data;Object.assign(form,{projectStatus:data.projectStatus||'',effectiveOn:draft.effectiveOn,changeNote:draft.changeNote})}
  catch(e){if(current===version)error.value=e.detail||e.message||'项目加载失败'}finally{if(current===version)loading.value=false}
}
async function save(){
  if(saving.value||loading.value||!await formRef.value.validate().catch(()=>false))return
  saving.value=true;error.value=''
  try{const chatDelivery=await deliveryRef.value.request(`${project.value.orderNo} · ${project.value.projectName}`,targetId);if(!chatDelivery)return;await saveAnnotationChatProgress({projectId:targetId,track:track.value,...form,chatDelivery});window.dispatchEvent(new CustomEvent('annotation-chat-progress-saved',{detail:{projectId:targetId,track:track.value}}));visible.value=false;ElMessage.success(track.value==='customer'?'已保存到该订单的客户进度':'已保存到该订单的项目进度')}
  catch(e){error.value=e.detail||e.message||'进度保存失败'}finally{saving.value=false}
}
defineExpose({open})
</script>
