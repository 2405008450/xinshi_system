<template>
  <div class="progress-delivery-fields" v-loading="loading">
    <el-form-item label="是否发送到该订单的会话"><el-radio-group :model-value="modelValue.sendToChat" :disabled="disabled" @update:model-value="setSend"><el-radio :value="false">只保存进度</el-radio><el-radio :value="true">保存并发送到会话</el-radio></el-radio-group></el-form-item>
    <template v-if="modelValue.sendToChat">
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link :disabled="disabled" @click="load">重试加载名单</el-button></el-alert>
      <el-alert v-else-if="!ready&&!loading" title="默认@配置尚未初始化，本次可手动选择人员。" type="info" :closable="false" />
      <el-form-item label="@ 人员／部门"><SummaryAudienceSelect v-model="audience" :users="users" :departments="departments" :disabled="disabled||loading" popper-class="annotation-progress-audience-popper" /></el-form-item>
      <p class="issue-hint">默认选中该项目的项目经理及统一默认名单，可增减人员或部门。发送时排除自己，@ 不在群内的人会加入该订单会话。</p>
    </template>
  </div>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import SummaryAudienceSelect from './SummaryAudienceSelect.vue'
import {annotationChatRequest} from '@/api/projectChat'
import {progressMentionSelection,expandProgressMentionDepartments} from '@/utils/annotationProgressMentions'
const props=defineProps({modelValue:{type:Object,required:true},projectId:String,project:Object,disabled:Boolean})
const emit=defineEmits(['update:modelValue','state'])
const loading=ref(false),error=ref(''),ready=ref(false),users=ref([]),departments=ref([])
const audience=computed({get:()=>({userIds:props.modelValue.userIds||[],departmentIds:props.modelValue.departmentIds||[]}),set:value=>emit('update:modelValue',{...props.modelValue,...expandProgressMentionDepartments(value,users.value)})})
let version=0
function setSend(value){emit('update:modelValue',{...props.modelValue,sendToChat:value})}
async function load(){
  const current=++version
  if(!props.projectId||!props.project)return
  loading.value=true;error.value='';ready.value=false;users.value=[];departments.value=[]
  try{const data=await annotationChatRequest('','progress-mention-defaults',{params:{scope:'progress'}});if(current!==version)return;ready.value=data.ready;users.value=data.users.filter(user=>user.id!==data.currentUserId);departments.value=data.departments;const initial={userIds:progressMentionSelection([...(data.automaticUserIds||[]),...data.userIds],props.project,users.value,data.currentUserId),departmentIds:data.departmentIds.filter(id=>data.departments.some(row=>row.id===id))};emit('update:modelValue',{...props.modelValue,...expandProgressMentionDepartments(initial,users.value)})}
  catch(e){if(current===version)error.value=e.detail||e.message||'加载名单失败'}finally{if(current===version)loading.value=false}
}
watch(()=>[props.projectId,props.project?.id],()=>{void load()},{immediate:true})
watch([loading,error],()=>emit('state',{loading:loading.value,error:error.value}),{immediate:true})
onBeforeUnmount(()=>{++version})
</script>
<style>.el-popper.annotation-progress-audience-popper{z-index:100030!important;max-width:calc(100vw - 32px)}</style>
<style scoped>.progress-delivery-fields{margin-top:18px;padding-top:16px;border-top:1px solid var(--el-border-color-lighter)}</style>
