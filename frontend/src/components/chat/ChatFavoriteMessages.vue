<template>
  <section class="favorite-messages" data-auto-draft="off">
    <div class="search"><el-input v-model="keyword" clearable placeholder="搜索消息、项目或客户名称" aria-label="搜索消息收藏" @keyup.enter="search"/><el-button @click="search">查询</el-button></div>
    <el-select ref="tagFilter" v-model="tagId" clearable filterable :append-to="filterAppendTo" aria-label="按收藏标签筛选" placeholder="全部收藏标签" @change="search" @visible-change="$event && loadTags()"><template #label="{label}"><ChatFavoriteTagLabel :name="label" :color="tags.find(tag=>tag.id===tagId)?.color||'#2563eb'"/></template><el-option v-for="tag in tags" :key="tag.id" :value="tag.id" :label="tag.name"><ChatFavoriteTagLabel :name="tag.name" :color="tag.color"/></el-option></el-select>
    <p role="status">消息收藏 · {{ total }} 条<span v-if="loading"> · 正在加载…</span></p>
    <p v-if="error" role="alert">{{ error }} <el-button link @click="load">重试</el-button></p>
    <div class="results" v-loading="loading">
      <el-empty v-if="!loading && !error && !items.length" description="暂无匹配的消息收藏" :image-size="45"/>
      <article v-for="item in items" :key="`${item.key}:${item.messageId}`"><button type="button" @click="$emit('locate',item)">
        <strong>{{ item.title }}</strong><small>{{ item.subtitle }} · {{ item.senderName }} · {{ formatBusinessDateTime(item.createdAt) }}</small><span>{{ screenshotPreview(item.preview) }}</span><small>打开会话并定位此消息 →</small>
      </button><div class="message-tags"><ChatFavoriteTagLabel v-for="tag in item.tags||[]" :key="tag.id" :name="tag.name" :color="tag.color" removable :disabled="busy.has(item.key+':'+item.messageId)" @remove="removeTag(item,tag)"/><span class="message-tag-actions"><el-button link size="small" :disabled="busy.has(item.key+':'+item.messageId)" @click="tagEditor.open(item.projectType,item.projectId,item.messageId)">标签</el-button><el-button link size="small" type="danger" :loading="busy.has(item.key+':'+item.messageId)" @click="unfavorite(item)">取消收藏</el-button></span></div></article>
    </div>
    <ChatListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :teleported="false"/>
    <ChatFavoriteTagEditor ref="tagEditor"/>
  </section>
</template>
<script setup>
import {onBeforeUnmount,onMounted,ref,shallowRef,watch} from 'vue'
import {chatRequest,unfavoriteProjectChatMessage} from '@/api/projectChat'
import {ElMessage} from 'element-plus'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {screenshotPreview} from '@/utils/screenshotReferences'
import ChatListPagination from './ChatListPagination.vue'
import ChatFavoriteTagEditor from './ChatFavoriteTagEditor.vue'
import ChatFavoriteTagLabel from './ChatFavoriteTagLabel.vue'
const emit=defineEmits(['locate','total'])
const keyword=ref(''),applied=ref(''),page=ref(1),pageSize=ref(20),items=ref([]),total=ref(0),loading=ref(false),error=ref('')
const tagId=ref(''),tags=ref([]),tagEditor=ref()
const tagFilter=ref(),filterAppendTo=shallowRef('body')
const busy=ref(new Set())
async function changeItem(item,action){const key=item.key+':'+item.messageId;if(busy.value.has(key))return;busy.value=new Set([...busy.value,key]);try{await action();await load()}catch(e){ElMessage.error(e.detail||e.message||'操作失败，请重试')}finally{busy.value=new Set([...busy.value].filter(id=>id!==key))}}
function removeTag(item,tag){return changeItem(item,()=>chatRequest(`favorite-tags/${item.projectType}/${item.projectId}/${item.messageId}`,{method:'put',data:{tagIds:(item.tags||[]).filter(row=>row.id!==tag.id).map(row=>row.id)}}))}
function unfavorite(item){return changeItem(item,()=>item.projectType==='discussion'?chatRequest(`discussions/${item.projectId}/message-actions/${item.messageId}/favorite`,{method:'delete'}):unfavoriteProjectChatMessage(item.messageId))}
let tagsVersion=0,disposed=false
async function loadTags(){const version=++tagsVersion,user=localStorage.getItem('user_id');try{const data=await chatRequest('favorite-tags');if(!disposed&&version===tagsVersion&&user===localStorage.getItem('user_id'))tags.value=data.items||[]}catch(e){if(!disposed)error.value=e.detail||e.message||'标签加载失败'}}
loadTags()
let timer,controller,generation=0
function search(){clearTimeout(timer);applied.value=keyword.value.trim();if(page.value!==1)page.value=1;else load()}
watch(keyword,value=>{clearTimeout(timer);if(!value.trim())search();else timer=setTimeout(search,400)})
async function load(){
 controller?.abort();controller=new AbortController();const current=controller,version=++generation,user=localStorage.getItem('user_id')
 loading.value=true;error.value='';items.value=[]
 try{const data=await chatRequest('messages/search',{params:{favorites_only:true,tag_id:tagId.value||undefined,keyword:applied.value,offset:(page.value-1)*pageSize.value,limit:pageSize.value},signal:current.signal});if(version!==generation||user!==localStorage.getItem('user_id'))return;items.value=data.items||[];total.value=data.total||0;if(page.value>1&&!items.value.length)page.value=Math.max(1,Math.ceil(total.value/pageSize.value))}
 catch(e){if(version===generation&&!current.signal.aborted)error.value=e.detail||e.message||'消息收藏加载失败'}finally{if(version===generation)loading.value=false}
}
watch(page,load);watch(pageSize,()=>{if(page.value!==1)page.value=1;else load()});load()
watch(total,value=>emit('total',value),{immediate:true})
function tagsChanged(){load();loadTags()}
onMounted(()=>{filterAppendTo.value=tagFilter.value?.$el?.closest('.el-popper')||'body';window.addEventListener('chat-favorite-tags-changed',tagsChanged)})
onBeforeUnmount(()=>{window.removeEventListener('chat-favorite-tags-changed',tagsChanged);disposed=true;++tagsVersion;clearTimeout(timer);++generation;controller?.abort()})
</script>
<style scoped>
.favorite-messages{display:flex;flex:1;min-height:0;flex-direction:column;overflow:hidden}.search{display:flex;gap:8px;padding:8px 0}.search>.el-input{flex:1;min-width:0}p{font-size:12px;color:#64748b;margin:6px 0}.results{flex:1;min-height:0;overflow-y:auto}.results article{border-bottom:1px solid #e2e8f0}.results article>button{display:flex;flex-direction:column;gap:7px;width:100%;border:0;background:white;padding:12px 6px;text-align:left;color:#1e293b;font:inherit;cursor:pointer}.results article>button:hover{background:#edf5ff}.results article>button:focus-visible{outline:2px solid #5479be;outline-offset:-2px}strong{font-size:13px;overflow-wrap:anywhere}small{font-size:11px;color:#64748b}button>span{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}.swatch{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}.message-tags{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:0 6px 9px}.message-tag-actions{display:inline-flex;gap:12px;margin-left:auto;flex:none}.message-tag-actions .el-button{margin:0}
</style>
