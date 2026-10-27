<template>
  <DraggableFormDialog v-model="visible" class="technical-picker-dialog" :z-index="100002" title="技术需求会话" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body>
    <div class="technical-picker"><el-input v-model="keyword" clearable placeholder="订单号、项目名称、需求内容（多关键词）" aria-label="搜索技术需求" @keyup.enter="query" /><p v-if="error" role="alert">{{error}} <el-button link @click="query">重试</el-button></p><el-table :data="rows" v-loading="loading" height="100%"><el-table-column prop="orderNo" label="订单号" width="175"/><el-table-column prop="title" label="项目名称" min-width="300" show-overflow-tooltip/><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click="openRoom(row)">打开会话</el-button></template></el-table-column></el-table><el-pagination :current-page="page" :page-size="50" :total="total" layout="total, prev, pager, next" @current-change="page=$event;load()" /></div>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {chatRequest} from '@/api/projectChat'
import {useProjectChatDock} from '@/composables/useProjectChatDock'
const visible=ref(false),keyword=ref(''),rows=ref([]),loading=ref(false),error=ref(''),page=ref(1),total=ref(0)
let controller,version=0,timer
async function load(){controller?.abort();const current=++version;controller=new AbortController();loading.value=true;error.value='';try{const data=await chatRequest('technical/rooms',{params:{keyword:keyword.value,offset:(page.value-1)*50,limit:50},signal:controller.signal});if(current===version){rows.value=data.items;total.value=data.total}}catch(e){if(current===version&&!controller.signal.aborted)error.value=e.message}finally{if(current===version)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
watch(keyword,value=>{clearTimeout(timer);if(visible.value){if(!value)query();else timer=setTimeout(query,400)}})
watch(visible,value=>{if(value)query();else{controller?.abort();version++;clearTimeout(timer)}})
function openRoom(row){useProjectChatDock().openChat({projectId:row.roomId,projectType:'discussion',title:row.title,subtitle:row.orderNo});visible.value=false}
onBeforeUnmount(()=>{controller?.abort();clearTimeout(timer)})
defineExpose({open:()=>{visible.value=true}})
</script>
<style>.technical-picker-dialog{height:66vh;min-height:min(420px,90vh)}</style>
<style scoped>.technical-picker{height:100%;min-height:0;display:flex;flex-direction:column;gap:12px}.technical-picker :deep(.el-table){flex:1;min-height:0}.technical-picker p{color:#b91c1c}</style>
