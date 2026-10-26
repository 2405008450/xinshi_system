<template>
  <DraggableFormDialog v-model="visible" title="消息引用关系" width="min(1180px, calc(100vw - 32px))" top="5vh" append-to-body class="chat-message-references" :z-index="dialogZ" @closed="cancel">
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load(true)">重试</el-button></el-alert>
    <p class="chat-message-references__count">共 {{ total }} 条引用 · 直接引用原消息 {{ directCount }} 条<span v-if="loading"> · 正在加载全部引用…</span></p>
    <p class="chat-message-references__hint">从上向下显示完整引用链，同一节点的不同引用左右分支。可滚动查看全部引用；点击引用对象可突出显示对应节点。</p>
    <div ref="listRef" class="chat-reference-graph" role="region" aria-label="完整引用链" tabindex="0">
      <ChatReferenceBranch v-if="graphRoot" :node="graphRoot" :project-type="projectType" :selected-id="selectedId" :highlighted-id="highlightedId" @focus="showNode" @locate="locate" />
    </div>
    <el-empty v-if="!loading && !error && !items.length" description="暂无引用" :image-size="44" />
    <template #footer><span v-if="loading">正在加载…</span><el-button :disabled="loading" @click="load(true)">刷新</el-button><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import ChatReferenceBranch from './ChatReferenceBranch.vue'
import { referenceGraphRoot } from '@/utils/chatReferenceTree'
import { computed,onBeforeUnmount, ref, watch } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { chatRequest } from '@/api/projectChat'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
const props=defineProps({projectId:{type:[String,Number],required:true},projectType:{type:String,required:true}})
const emit=defineEmits(['locate'])
const visible=ref(false),original=ref(null),items=ref([]),total=ref(0),hasMore=ref(false),loading=ref(false),error=ref(''),dialogZ=ref(2120)
const directCount=ref(0),selectedId=ref(''),highlightedId=ref(''),listRef=ref()
const graphRoot=computed(()=>referenceGraphRoot(original.value,items.value))
function showNode(id){highlightedId.value=id;const target=[...(listRef.value?.querySelectorAll('[data-reference-id]')||[])].find(el=>el.dataset.referenceId===String(id));target?.scrollIntoView({behavior:'smooth',block:'center',inline:'nearest'})}
let messageId='',controller,version=0
function open(id,event) { cancel();messageId=String(id);items.value=[];original.value=null;total.value=0;hasMore.value=false;dialogZ.value=chatOverlayZIndex(event?.currentTarget);visible.value=true;void load(true) }
function cancel(){++version;controller?.abort();loading.value=false}
async function load(reset){
  if(loading.value||!messageId)return
  controller=new AbortController();const current=++version;loading.value=true;error.value=''
  try{
    let offset=0
    if(reset)items.value=[]
    do{
      const data=await chatRequest(`conversations/${props.projectType}/${props.projectId}/messages/${messageId}/references`,{params:{offset,limit:50},signal:controller.signal})
      if(current!==version)return
      original.value=data.original;selectedId.value=data.selectedMessageId || messageId;directCount.value=data.directCount || 0
      items.value=[...new Map([...items.value,...(data.items||[])].map(row=>[String(row.id),row])).values()];total.value=data.total;hasMore.value=data.hasMore
      offset+=data.items?.length || 0
      if(data.hasMore && !data.items?.length)throw new Error('引用列表加载不完整，请刷新重试')
    }while(hasMore.value)

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
.chat-message-references__count,.chat-message-references__hint{font-size:12px;color:#64748b;margin:4px 0 10px;line-height:1.6}
.chat-reference-graph{overflow:auto;max-height:calc(70vh - 120px);min-height:160px;padding:14px 8px 20px;box-sizing:border-box;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc}
.chat-reference-graph:focus-visible{outline:2px solid #93c5fd;outline-offset:2px}
.chat-reference-graph>:deep(.reference-branch){min-width:100%}
</style>
