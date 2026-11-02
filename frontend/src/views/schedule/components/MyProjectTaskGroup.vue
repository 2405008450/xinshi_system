<template>
  <div class="my-project-group">
    <div class="project-search"><el-input v-model="keyword" clearable placeholder="搜索订单号、项目名称或客户" @keyup.enter="query" /><el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!ready" title="项目安排尚未初始化" type="info" :closable="false" />
    <el-table :data="rows" v-loading="loading" border size="small" row-key="id">
      <el-table-column prop="order_no" label="订单号" width="165"><template #default="{row}"><el-button link type="primary" @click="$emit('open-project',row)">{{row.order_no}}</el-button></template></el-table-column>
      <el-table-column prop="project_name" label="项目名称" min-width="260" show-overflow-tooltip />
      <el-table-column prop="client_short_name" label="客户简称" min-width="140" show-overflow-tooltip />
      <el-table-column label="项目状态" width="145"><template #default="{row}">{{getProjectStatusLabel(row.project_type,row.project_status)}}</template></el-table-column>
      <el-table-column label="操作" :width="group==='interpretation'?210:115" fixed="right"><template #default="{row}"><el-button v-if="group==='interpretation'" link type="primary" @click="openAnnotationWorkStatus({mode:'arrangement',projectType:'interpretation',projectId:row.id})">今日安排</el-button><el-button link type="primary" @click="$emit('open-project',row)">进入项目</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
  </div>
</template>
<script setup>
import {onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {getMyProjectTasks} from '@/api/tasks'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {openAnnotationWorkStatus} from '@/utils/annotationWorkStatus'
const props=defineProps({group:{type:String,required:true}})
const emit=defineEmits(['open-project','count-change'])
const rows=ref([]),total=ref(0),page=ref(1),keyword=ref(''),loading=ref(false),ready=ref(true),error=ref('')
let timer,controller,sequence=0
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';try{const result=await getMyProjectTasks({group:props.group,keyword:keyword.value,page:page.value,page_size:10},{signal:controller.signal});if(id!==sequence)return;rows.value=result.items;total.value=result.total;ready.value=result.ready;emit('count-change',result.total)}catch(err){if(id===sequence&&err.code!=='ERR_CANCELED')error.value=err.detail||'读取本人项目失败，请点击查询重试'}finally{if(id===sequence)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
function reset(){keyword.value='';query()}
watch(keyword,value=>{clearTimeout(timer);controller?.abort();sequence++;loading.value=false;if(!value)query();else timer=setTimeout(query,400)})
function onArrangementUpdated(){if(props.group==='interpretation')load()}
onMounted(()=>{load();window.addEventListener('interpretation-work-arrangement-updated',onArrangementUpdated)})
onBeforeUnmount(()=>{window.removeEventListener('interpretation-work-arrangement-updated',onArrangementUpdated);clearTimeout(timer);controller?.abort();sequence++})
</script>
<style scoped>.project-search{display:flex;gap:8px;margin:10px 0}.project-search .el-input{max-width:420px}.el-pagination{margin-top:12px;justify-content:flex-end;overflow-x:auto}.el-alert{margin-bottom:10px}</style>
