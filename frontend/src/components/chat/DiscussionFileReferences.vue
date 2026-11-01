<template><span class="discussion-files"><span v-for="id in ids" :key="id"><el-button link :loading="busy[id]" @click.stop="download(id)">📎 {{ names[id] || '下载附件' }}</el-button><el-button v-if="removable" link aria-label="移除附件" @click="$emit('remove',id)">×</el-button></span></span></template>
<script setup>
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
const props=defineProps({text:String,roomId:String,removable:Boolean})
defineEmits(['remove'])
const ids=computed(()=>[...new Set(Array.from((props.text||'').matchAll(/\[附件\]\(discussion-file:\/\/([0-9a-f-]{36})\)/gi),match=>match[1]))])
const names=reactive({}),busy=reactive({})
const path=id=>`/chat/discussions/${props.roomId}/files/${id}`
watch(()=>[props.roomId,props.text],()=>{const room=props.roomId;for(const id of ids.value)api.get(path(id),{params:{info:true}}).then(data=>{if(room===props.roomId)names[id]=data.name}).catch(()=>{})},{immediate:true})
async function download(id){busy[id]=true;let url;try{const blob=await api.get(path(id),{responseType:'blob'});url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=names[id]||'附件';link.click()}catch{ElMessage.error('附件下载失败，请重试')}finally{busy[id]=false;if(url)setTimeout(()=>URL.revokeObjectURL(url),1000)}}
</script>
<style scoped>.discussion-files{display:flex;flex-direction:column;align-items:flex-start;max-width:100%}.discussion-files>span{display:flex;max-width:100%;overflow-wrap:anywhere}</style>
