<template><span class="screenshot-text"><span v-if="showText" class="screenshot-plain">{{ plain }}</span><span class="screenshot-previews"><span v-for="id in ids" :key="id" class="screenshot-preview"><el-image v-if="urls[id]" :src="urls[id]" :preview-src-list="Object.values(urls)" preview-teleported fit="contain" @click.stop /><span v-else>{{ errors[id]||'正在加载截图…' }}</span><button v-if="removable" type="button" aria-label="移除截图" @click.stop="$emit('remove',id)">×</button></span></span></span></template>
<script setup>
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import api from '@/api'
import { screenshotIds,screenshotText } from '@/utils/screenshotReferences'
const props=defineProps({text:{type:String,default:''},showText:{type:Boolean,default:true},removable:Boolean,chatMessageId:[String,Number],chatKind:String})
defineEmits(['remove'])
const ids=computed(()=>screenshotIds(props.text)),plain=computed(()=>screenshotText(props.text)),urls=ref({}),errors=ref({})
let version=0
watch(()=>[props.text,props.chatMessageId],async()=>{const current=++version;for(const id of Object.keys(urls.value))if(!ids.value.includes(id)){URL.revokeObjectURL(urls.value[id]);delete urls.value[id]}
  await Promise.all(ids.value.map(async id=>{if(urls.value[id])return;try{const blob=await api.get(`/editor-screenshots/${id}`,{responseType:'blob',timeout:60000,screenshotIds:[id],params:props.chatMessageId?{chat_message_id:props.chatMessageId,chat_kind:props.chatKind||'project'}:{}});if(current===version)urls.value[id]=URL.createObjectURL(blob)}catch(e){if(current===version)errors.value[id]=[404,410].includes(e.response?.status||e.status)?'截图已过期或不存在':e.detail||'请重新打开记录以查看截图'}}))
},{immediate:true})
onBeforeUnmount(()=>{++version;Object.values(urls.value).forEach(URL.revokeObjectURL)})
</script>
<style scoped>.screenshot-text{display:inline-flex;flex-direction:column;max-width:100%;white-space:normal;vertical-align:top}.screenshot-plain{white-space:pre-wrap;overflow-wrap:anywhere}.screenshot-previews{display:flex;flex-wrap:wrap;gap:8px;margin-top:5px}.screenshot-preview{position:relative;display:inline-flex;flex-direction:column;max-width:280px;min-width:80px;font-size:11px;color:#94a3b8}.screenshot-preview .el-image{max-width:280px;height:130px;border:1px solid #e2e8f0;border-radius:6px}.screenshot-preview button{position:absolute;right:0;top:0;width:22px;height:22px;border:1px solid #cbd5e1;background:white;border-radius:4px;cursor:pointer}</style>
