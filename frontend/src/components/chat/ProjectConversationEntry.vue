<template><el-button link type="primary" :loading="busy" :disabled="!error && (!status || (!status.joined&&!status.canCreate))" @click.stop="enter">{{ error ? '重试会话状态' : status?.created ? '进入会话' : '创建会话' }}</el-button></template>
<script setup>
import {onMounted,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {chatRequest} from '@/api/projectChat'
import {useAnnotationFollowed} from '@/composables/useAnnotationFollowed'
import {useProjectChatDock} from '@/composables/useProjectChatDock'
const props=defineProps({module:{type:String,required:true},projectId:{type:String,required:true}})
const status=ref(),busy=ref(false),error=ref(false),requestKey=crypto.randomUUID()
const {openChat,revealSession}=useProjectChatDock()
const {refresh}=useAnnotationFollowed()
async function load(){busy.value=true;error.value=false;try{status.value=await chatRequest(`project-entry/${props.module}/${props.projectId}`)}catch(e){error.value=true;ElMessage.error(e.detail||'会话状态加载失败')}finally{busy.value=false}}
async function enter(){if(busy.value)return;if(error.value)return load();busy.value=true;try{const data=status.value.joined?status.value:await chatRequest(`project-entry/${props.module}/${props.projectId}`,{method:'post',data:{request_key:requestKey}});status.value=data;if(data.target){revealSession(data.target);openChat(data.target);void refresh({force:true})}}catch(e){ElMessage.error(e.detail||'打开会话失败')}finally{busy.value=false}}
onMounted(load)
</script>
