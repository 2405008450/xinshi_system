<template>
  <DraggableFormDialog v-model="visible" title="消息引用与回复" width="min(660px, calc(100vw - 32px))" top="5vh" append-to-body class="chat-message-references" :z-index="dialogZ" @closed="cancel">
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load(true)">重试</el-button></el-alert>
    <section v-if="original" class="chat-message-references__original"><strong>原消息 · {{ original.senderName }}</strong><time>{{ formatBusinessDateTime(original.createdAt) }}</time><p><ScreenshotText :text="original.content" :chat-message-id="original.id" :chat-kind="projectType" /></p><el-button v-if="!original.recalledAt" link @click="locate(original.id)">定位原消息</el-button></section>
    <p class="chat-message-references__count">共 {{ total }} 条引用回复</p>
    <div v-for="row in items" :key="row.id" class="chat-message-references__item"><strong>{{ row.senderName }}</strong><time>{{ formatBusinessDateTime(row.createdAt) }}</time><p><ScreenshotText :text="row.content" :chat-message-id="row.id" :chat-kind="projectType" /></p><el-button link @click="locate(row.id)">定位消息</el-button></div>
    <el-empty v-if="!loading && !error && !items.length" description="暂无引用回复" :image-size="44" />
    <template #footer><span v-if="loading">正在加载…</span><el-button :disabled="loading" @click="load(true)">刷新</el-button><el-button v-if="hasMore" :loading="loading" @click="load(false)">加载更多</el-button><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { chatRequest } from '@/api/projectChat'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props=defineProps({projectId:{type:[String,Number],required:true},projectType:{type:String,required:true}})
const emit=defineEmits(['locate'])
const visible=ref(false),original=ref(null),items=ref([]),total=ref(0),hasMore=ref(false),loading=ref(false),error=ref(''),dialogZ=ref(2120)
let messageId='',controller,version=0
function open(id,event) { cancel();messageId=String(id);items.value=[];original.value=null;total.value=0;hasMore.value=false;dialogZ.value=chatOverlayZIndex(event?.currentTarget);visible.value=true;void load(true) }
function cancel(){++version;controller?.abort();loading.value=false}
async function load(reset){
  if(loading.value||!messageId)return
  controller=new AbortController();const current=++version;loading.value=true;error.value=''
  try{
    const data=await chatRequest(`conversations/${props.projectType}/${props.projectId}/messages/${messageId}/references`,{params:{offset:reset?0:items.value.length,limit:30},signal:controller.signal})
    if(current!==version)return
    original.value=data.original;items.value=[...new Map([...(reset?[]:items.value),...(data.items||[])].map(row=>[String(row.id),row])).values()];total.value=data.total;hasMore.value=data.hasMore
  }catch(e){if(current===version&&e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'引用回复加载失败'}
  finally{if(current===version)loading.value=false}
}
function locate(id){visible.value=false;emit('locate',id)}
onBeforeUnmount(cancel)
watch(() => [props.projectId,props.projectType], () => { cancel();visible.value=false;original.value=null;items.value=[];messageId='' })
defineExpose({open})
</script>
<style>
.chat-message-references{display:flex;flex-direction:column;max-height:85vh;overflow:hidden}.chat-message-references>.el-dialog__header,.chat-message-references>.el-dialog__footer{flex:none}.chat-message-references>.el-dialog__body{min-height:0;overflow-y:auto}.chat-message-references>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
<style scoped>
.chat-message-references__original{padding:12px;background:#eff6ff;border-left:3px solid #60a5fa;border-radius:5px}.chat-message-references__count{font-size:12px;color:#64748b}.chat-message-references__item{padding:12px 0;border-bottom:1px solid #e2e8f0}.chat-message-references time{display:block;font-size:11px;color:#64748b;margin-top:4px}.chat-message-references p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}
</style>
