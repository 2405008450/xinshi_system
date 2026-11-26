<template>
  <DraggableFormDialog v-model="visible" class="technical-picker-dialog" :z-index="100002" title="技术需求会话" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body>
    <div class="technical-picker">
      <el-input v-model="keyword" clearable placeholder="订单号、项目名称、需求内容（多关键词）" aria-label="搜索技术需求" @keyup.enter="query"><template #append><el-button @click="query">查询</el-button></template></el-input>
      <p class="technical-picker__count" role="status">我参与的技术需求：共 {{ total }} 个<span v-if="rows.length">，当前显示 {{ (page - 1) * pageSize + 1 }}—{{ (page - 1) * pageSize + rows.length }}</span></p>
      <p v-if="error" role="alert">{{ error }} <el-button link @click="load">重试</el-button></p>
      <el-table :data="rows" v-loading="loading" height="100%" empty-text="暂无符合条件的技术需求会话">
        <el-table-column prop="folderDay" label="日期" width="110" />
        <el-table-column prop="orderNo" label="订单号" width="175" />
        <el-table-column prop="title" label="项目名称" min-width="280"><template #default="{row}"><span class="technical-picker__title">{{ row.title }}</span></template></el-table-column>
        <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" @click="openRoom(row)">打开会话</el-button></template></el-table-column>
      </el-table>
      <ChatListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
    </div>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import ChatListPagination from './ChatListPagination.vue'
import {chatRequest} from '@/api/projectChat'
import {useProjectChatDock} from '@/composables/useProjectChatDock'
const visible=ref(false),keyword=ref(''),rows=ref([]),loading=ref(false),error=ref(''),page=ref(1),pageSize=ref(20),total=ref(0)
let controller,version=0,timer
async function load(){controller?.abort();const current=++version,identity=localStorage.getItem('user_id');controller=new AbortController();const request=controller;loading.value=true;error.value='';rows.value=[];try{const data=await chatRequest('technical/rooms',{params:{keyword:keyword.value,offset:(page.value-1)*pageSize.value,limit:pageSize.value},signal:request.signal});if(current===version&&identity===localStorage.getItem('user_id')){total.value=data.total;const last=Math.max(1,Math.ceil(total.value/pageSize.value));if(page.value>last){page.value=last;return load()}rows.value=data.items}}catch(e){if(current===version&&!request.signal.aborted)error.value=e.detail||e.message}finally{if(current===version)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
watch(keyword,value=>{clearTimeout(timer);if(visible.value){if(!value)query();else timer=setTimeout(query,400)}})
watch(visible,value=>{if(value)query();else{controller?.abort();version++;clearTimeout(timer)}})
function openRoom(row){useProjectChatDock().openChat({projectId:row.roomId,projectType:'discussion',title:row.title,subtitle:row.orderNo});visible.value=false}
onBeforeUnmount(()=>{controller?.abort();clearTimeout(timer)})
defineExpose({open:()=>{visible.value=true}})
</script>
<style>
.technical-picker-dialog.el-dialog{display:flex;flex-direction:column;height:min(720px,86vh);max-height:90vh;overflow:hidden}
.technical-picker-dialog>.el-dialog__header,.technical-picker-dialog>.el-dialog__footer{flex:none}
.technical-picker-dialog>.el-dialog__body{display:flex;flex:1;min-height:0;overflow:hidden}
.technical-picker-dialog>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
<style scoped>
.technical-picker{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column;gap:10px}
.technical-picker>.el-input,.technical-picker>.el-pagination,.technical-picker>p{flex:none}
.technical-picker :deep(.el-table){flex:1;min-height:0}
.technical-picker__title{white-space:normal;overflow-wrap:anywhere}
.technical-picker p{margin:0;color:#b91c1c;font-size:12px}
.technical-picker .technical-picker__count{color:#64748b}
.technical-picker>.el-pagination{max-width:100%;overflow-x:auto}
</style>
