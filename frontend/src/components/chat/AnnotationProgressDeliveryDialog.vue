<template>
  <DraggableFormDialog v-model="visible" :title="defaultsMode?(scope==='creation'?'新增标注项目 · 默认@':'标注项目 · 默认@'):(scope==='creation'?'新增项目并同步会话':'保存进度并同步会话')" width="min(680px, calc(100vw - 32px))" top="7vh" class="issue-dialog" append-to-body :z-index="100010" @closed="cancel">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!ready && !loading" title="默认@配置尚未初始化；本次仍可手动选择发送名单。" type="info" :closable="false" />
    <AppForm :model="form" label-position="top" v-loading="loading">
      <p v-if="defaultsMode">{{ scope==='creation'?'新增标注项目默认 @ 赵震锋，可以调整此统一名单。':'所有标注项目默认优先 @ 该项目的项目经理，下方设置额外默认名单。' }}所有账号共用，发送前可临时增删；这里只设置预选对象，不会发消息或修改已有参与人。</p>
      <template v-else>
        <p>{{ projectLabel }}</p>
        <el-form-item label="是否发送到该订单的会话"><el-radio-group v-model="form.sendToChat"><el-radio :value="false">只保存进度</el-radio><el-radio :value="true">保存并发送到会话</el-radio></el-radio-group></el-form-item>
      </template>
      <el-form-item v-if="defaultsMode || form.sendToChat" label="@ 人员／部门">
        <SummaryAudienceSelect v-model="audience" :users="users" :departments="departments" popper-class="annotation-progress-audience-popper" />
      </el-form-item>
      <p v-if="defaultsMode || form.sendToChat" class="issue-hint">可选择全部人员或全部部门。仅通知有项目沟通权限的有效账号，发送时排除自己；@ 不在群内的人会同时将其加入该订单会话。</p>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="dismiss">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading || (defaultsMode && (!ready || !canManage || !!error)) || (form.sendToChat && !!error) || (scope==='creation' && !!error)" @click="confirm">{{ defaultsMode?'保存默认名单':form.sendToChat?'确认保存并发送':'确认仅保存' }}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import SummaryAudienceSelect from './SummaryAudienceSelect.vue'
import { annotationChatRequest } from '@/api/projectChat'
import { getAnnotationProject } from '@/api/annotationProjects'
import { progressMentionSelection, expandProgressMentionDepartments } from '@/utils/annotationProgressMentions'
import '@/views/resource/components/issueDialogs.css'
const visible=ref(false),defaultsMode=ref(false),loading=ref(false),saving=ref(false),ready=ref(false),canManage=ref(false),error=ref(''),users=ref([]),departments=ref([]),projectLabel=ref(''),selection=ref({userIds:[],departmentIds:[]})
const form=reactive({sendToChat:false})
const scope=ref('progress')
const audience=computed({get:()=>selection.value,set:value=>{selection.value=defaultsMode.value?value:expandProgressMentionDepartments(value,users.value)}})
let resolvePending,version=0
function cancel(){resolvePending?.(null);resolvePending=undefined}
function dismiss(){visible.value=false;cancel()}
async function load(mode,label='',projectId='',settingScope='progress'){
  cancel();const current=++version;defaultsMode.value=mode;projectLabel.value=label;visible.value=true;loading.value=true;error.value='';ready.value=false;form.sendToChat=true;selection.value={userIds:[],departmentIds:[]};users.value=[];departments.value=[]
  scope.value=settingScope
  try{const [data,project]=await Promise.all([annotationChatRequest('','progress-mention-defaults',{params:{scope:settingScope}}),!mode&&projectId?getAnnotationProject(projectId):Promise.resolve(null)]);if(current!==version)return;if(settingScope==='creation'&&!data.supportsCreation)throw new Error('新增项目默认@及截图功能等待后端更新，请稍后重试');ready.value=data.ready;canManage.value=data.canManage;users.value=data.users.filter(u=>mode||u.id!==data.currentUserId);departments.value=data.departments;const defaults=[...(data.automaticUserIds||[]),...data.userIds];const initial={userIds:mode?[...new Set(defaults)].filter(id=>users.value.some(u=>u.id===id)):progressMentionSelection(defaults,project,users.value,data.currentUserId),departmentIds:data.departmentIds.filter(id=>data.departments.some(d=>d.id===id))};selection.value=mode?initial:expandProgressMentionDepartments(initial,users.value)}
  catch(e){if(current===version)error.value=e.detail||e.message||'加载名单失败'}finally{if(current===version)loading.value=false}
}
function request(label,projectId,settingScope='progress'){void load(false,label,projectId,settingScope);return new Promise(resolve=>{resolvePending=resolve})}
async function confirm(){
  if(loading.value||saving.value)return
  if(scope.value==='creation'&&error.value)return
  if(!defaultsMode.value){const resolve=resolvePending;resolvePending=undefined;visible.value=false;resolve?.({sendToChat:form.sendToChat,...selection.value});return}
  saving.value=true;error.value=''
  try{await annotationChatRequest('','progress-mention-defaults',{method:'put',params:{scope:scope.value},data:selection.value});visible.value=false;ElMessage.success('所有标注项目的默认@名单已更新')}
  catch(e){error.value=e.detail||e.message||'保存失败'}finally{saving.value=false}
}
onBeforeUnmount(()=>{++version;cancel()})
defineExpose({request,openDefaults:()=>load(true),openCreationDefaults:()=>load(true,'','','creation')})
</script>
<style>.el-popper.annotation-progress-audience-popper{z-index:100030!important;max-width:calc(100vw - 32px)}</style>
