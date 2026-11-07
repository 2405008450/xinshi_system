<template>
  <DraggableFormDialog :model-value="modelValue" title="编号删除记录" width="min(1080px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @update:model-value="$emit('update:modelValue',$event)">
    <div class="number-history-search"><span>关键词</span><el-input v-model="keyword" clearable placeholder="编号、原名称、删除人，可输入多个关键词" @input="queueSearch" @keyup.enter="search" /><el-button @click="search">查询</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p class="number-history-help">同一编号重新使用后，每次删除的原记录仍分别保留。</p>
    <el-table v-loading="loading" :data="rows" row-key="id" border empty-text="暂无删除记录" max-height="480">
      <el-table-column prop="number" label="原编号" min-width="180" />
      <el-table-column prop="entity_name" label="原名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="actor_name" label="删除人" width="130" />
      <el-table-column label="删除时间" min-width="190"><template #default="{row}">{{formatBusinessDateTime(row.deleted_at)}}</template></el-table-column>
      <el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><el-popover title="删除记录详情" trigger="click" placement="left" :width="760"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="number-history-details"><el-descriptions :column="2" border size="small"><el-descriptions-item label="原编号">{{row.number}}</el-descriptions-item><el-descriptions-item label="删除人">{{row.actor_name}}</el-descriptions-item><el-descriptions-item label="原名称" :span="2">{{row.entity_name||'-'}}</el-descriptions-item><el-descriptions-item label="删除时间" :span="2">{{formatBusinessDateTime(row.deleted_at)}}</el-descriptions-item><el-descriptions-item v-for="field in fields(row.snapshot)" :key="field.key" :label="field.label" :span="field.long?2:1">{{field.value}}</el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total,prev,pager,next" @current-change="load" />
    <template #footer><el-button @click="$emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import api from '@/api'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {getProjectStatusLabel} from '@/utils/projectStatus'
const props=defineProps({modelValue:Boolean,kind:String,number:String})
defineEmits(['update:modelValue'])
const keyword=ref(''),rows=ref([]),total=ref(0),page=ref(1),loading=ref(false),error=ref('')
let controller,timer,sequence=0
async function load(){
  const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value=''
  try{const data=await api.get('/business-numbers/history',{params:{kind:props.kind,keyword:keyword.value,skip:(page.value-1)*20,limit:20},signal:controller.signal});if(current===sequence){rows.value=data.items;total.value=data.total}}
  catch(cause){if(current===sequence&&cause.code!=='ERR_CANCELED')error.value=cause.message||'删除记录加载失败'}
  finally{if(current===sequence)loading.value=false}
}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);if(!keyword.value.trim())search();else timer=setTimeout(search,400)}
const labels={client_name:'客户全称',client_short_name:'客户简称',project_status:'原项目状态',status:'原状态',customer_reception_time:'客户接单时间',customer_deadline_time:'客户交稿时间',language_pair:'翻译方向',service_content:'服务内容',contact_name:'客户联系人',client_manager:'客户经理',demand_no:'原需求编号',request_date:'需求日期',position:'岗位',headcount:'人数',reason:'原因',details:'具体内容',content:'任务内容',full_name:'姓名',primary_phone:'电话',primary_email:'邮箱',received_at:'接单时间',remarks:'备注',follow_up:'跟进情况',work_date:'工作日期'}
function valueFor(key,value){if(/(_time|_at)$/.test(key))return formatBusinessDateTime(value);if(['project_status','status'].includes(key)){const type=props.kind?.replace('_suborder','');if(['translation','interpretation','annotation','recruitment'].includes(type))return getProjectStatusLabel(type,value);return {active:'启用',inactive:'停用',standby:'待安排',completed:'已完成',pending:'待处理',cancelled:'已取消',confirmed:'已确认'}[value]||String(value)}return String(value)}
function fields(snapshot={}){return Object.entries(labels).filter(([key])=>snapshot[key]!==null&&snapshot[key]!==undefined&&snapshot[key]!=='').map(([key,label])=>({key,label,value:valueFor(key,snapshot[key]),long:['details','content','remarks','follow_up'].includes(key)}))}
watch(()=>props.modelValue,visible=>{if(visible){keyword.value=props.number||'';search()}else{sequence++;controller?.abort();clearTimeout(timer)}},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
</script>
<style scoped>
.number-history-search{display:flex;align-items:center;gap:12px;margin-bottom:12px}.number-history-search .el-input{flex:1}.number-history-help{color:var(--el-text-color-secondary);font-size:13px}.number-history-details{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}.el-pagination{margin-top:12px}
</style>
