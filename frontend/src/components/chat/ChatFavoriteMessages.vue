<template>
  <section class="favorite-messages" data-auto-draft="off">
    <div class="search"><el-input v-model="keyword" clearable placeholder="搜索消息、项目或客户名称" aria-label="搜索消息收藏" @keyup.enter="search"/><el-button @click="search">查询</el-button></div>
    <p role="status">消息收藏 · {{ total }} 条<span v-if="loading"> · 正在加载…</span></p>
    <p v-if="error" role="alert">{{ error }} <el-button link @click="load">重试</el-button></p>
    <div class="results" v-loading="loading">
      <el-empty v-if="!loading && !error && !items.length" description="暂无匹配的消息收藏" :image-size="45"/>
      <button v-for="item in items" :key="`${item.key}:${item.messageId}`" type="button" @click="$emit('locate',item)">
        <strong>{{ item.title }}</strong><small>{{ item.subtitle }} · {{ item.senderName }} · {{ formatBusinessDateTime(item.createdAt) }}</small><span>{{ screenshotPreview(item.preview) }}</span><small>打开会话并定位此消息 →</small>
      </button>
    </div>
    <ChatListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :teleported="false"/>
  </section>
</template>
<script setup>
import {onBeforeUnmount,ref,watch} from 'vue'
import {chatRequest} from '@/api/projectChat'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {screenshotPreview} from '@/utils/screenshotReferences'
import ChatListPagination from './ChatListPagination.vue'
const emit=defineEmits(['locate','total'])
const keyword=ref(''),applied=ref(''),page=ref(1),pageSize=ref(20),items=ref([]),total=ref(0),loading=ref(false),error=ref('')
let timer,controller,generation=0
function search(){clearTimeout(timer);applied.value=keyword.value.trim();if(page.value!==1)page.value=1;else load()}
watch(keyword,value=>{clearTimeout(timer);if(!value.trim())search();else timer=setTimeout(search,400)})
async function load(){
 controller?.abort();controller=new AbortController();const current=controller,version=++generation,user=localStorage.getItem('user_id')
 loading.value=true;error.value='';items.value=[]
 try{const data=await chatRequest('messages/search',{params:{favorites_only:true,keyword:applied.value,offset:(page.value-1)*pageSize.value,limit:pageSize.value},signal:current.signal});if(version!==generation||user!==localStorage.getItem('user_id'))return;items.value=data.items||[];total.value=data.total||0;if(page.value>1&&!items.value.length)page.value=Math.max(1,Math.ceil(total.value/pageSize.value))}
 catch(e){if(version===generation&&!current.signal.aborted)error.value=e.detail||e.message||'消息收藏加载失败'}finally{if(version===generation)loading.value=false}
}
watch(page,load);watch(pageSize,()=>{if(page.value!==1)page.value=1;else load()});load()
watch(total,value=>emit('total',value),{immediate:true})
onBeforeUnmount(()=>{clearTimeout(timer);++generation;controller?.abort()})
</script>
<style scoped>
.favorite-messages{display:flex;flex:1;min-height:0;flex-direction:column;overflow:hidden}.search{display:flex;gap:8px;padding:8px 0}.search>.el-input{flex:1;min-width:0}p{font-size:12px;color:#64748b;margin:6px 0}.results{flex:1;min-height:0;overflow-y:auto}.results>button{display:flex;flex-direction:column;gap:7px;width:100%;border:0;border-bottom:1px solid #e2e8f0;background:white;padding:12px 6px;text-align:left;color:#1e293b;font:inherit;cursor:pointer}.results>button:hover{background:#edf5ff}.results>button:focus-visible{outline:2px solid #5479be;outline-offset:-2px}strong{font-size:13px;overflow-wrap:anywhere}small{font-size:11px;color:#64748b}span{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
</style>
