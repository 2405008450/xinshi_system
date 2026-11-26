<template>
  <section class="meeting-assigned-tasks" data-auto-draft="off">
    <div class="assigned-toolbar"><h4>会议安排的{{category==='project'?'项目':'非项目'}}任务</h4><el-input v-model="keyword" clearable placeholder="搜索具体任务" @keyup.enter="query" /><el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button><el-button @click="load">刷新</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border size="small"><el-table-column label="具体任务" min-width="260"><template #default="{row}">{{row.content}}<small v-if="row.project?.order_no">{{row.project.project_type}} · {{row.project.order_no}} · {{row.project.project_name}}</small></template></el-table-column><el-table-column prop="arranger_name" label="安排人" width="110" /><el-table-column label="安排时间" min-width="180"><template #default="{row}">{{formatBusinessDateTime(row.assigned_at)}}</template></el-table-column><el-table-column label="完成时间" min-width="180"><template #default="{row}"><span :class="{'assigned-overdue':row.status!=='completed'&&Date.parse(row.due_at)<clock}">{{formatBusinessDateTime(row.due_at)}}</span></template></el-table-column><el-table-column label="状态" width="140"><template #default="{row}"><el-select :model-value="row.status" :disabled="saving" @change="change(row,$event)"><el-option v-for="(name,key) in labels" :key="key" :value="key" :label="name" /></el-select></template></el-table-column><el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><el-button v-if="row.can_view_meeting" link type="primary" @click="openMeeting(row)">查看会议</el-button><span v-else>会议委派任务</span></template></el-table-column></el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
  </section>
</template>
<script setup>
import {onMounted,onBeforeUnmount,ref} from 'vue'
import {watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getMeetingTasks,updateMeetingTask} from '@/api/meetings'
import {formatBusinessDateTime} from '@/utils/dateTime'
const props=defineProps({category:{type:String,required:true}})
const rows=ref([]),total=ref(0),page=ref(1),keyword=ref(''),loading=ref(false),error=ref(''),saving=ref(false),clock=ref(Date.now())
const labels={pending:'待进行',in_progress:'进行中',completed:'已完成'}
let controller,sequence=0,timer
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';clock.value=Date.now();try{const result=await getMeetingTasks({category:props.category,keyword:keyword.value,page:page.value,page_size:10},controller.signal);if(id===sequence){rows.value=result.items;total.value=result.total}}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'会议任务读取失败'}finally{if(id===sequence)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
function reset(){keyword.value='';query()}
watch(keyword,value=>{clearTimeout(timer);controller?.abort();sequence++;if(value)timer=setTimeout(query,400);else query()})
async function change(row,status){saving.value=true;try{Object.assign(row,await updateMeetingTask(row.id,{status,revision:row.revision}));ElMessage.success('任务状态已更新')}catch(e){ElMessage.error(e.detail||'任务更新失败');load()}finally{saving.value=false}}
function openMeeting(row){window.dispatchEvent(new CustomEvent('meeting-open',{detail:{meetingId:row.meeting_id}}))}
onMounted(()=>{load();window.addEventListener('meeting-tasks-changed',load);window.addEventListener('focus',load)})
onBeforeUnmount(()=>{controller?.abort();sequence++;clearTimeout(timer);window.removeEventListener('meeting-tasks-changed',load);window.removeEventListener('focus',load)})
</script>
<style scoped>.meeting-assigned-tasks{margin:14px 0;border:1px solid #dbe3ec;padding:14px;border-radius:6px}.assigned-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px}.assigned-toolbar h4{margin:0 auto 0 0}.assigned-toolbar .el-input{max-width:280px}.assigned-overdue{color:#dc2626}small{display:block;color:#64748b}.el-pagination{margin-top:12px;justify-content:flex-end;overflow-x:auto}</style>
