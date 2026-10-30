<template>
  <section v-if="record" class="technical-requirements">
    <div class="technical-requirements__heading"><strong>{{record.title}}</strong><ChatProjectActions :project-id="record.projectId" project-type="annotation" icon-only><template #detail-reference><el-button link type="primary" :aria-label="`查看项目详情 ${record.orderNo}`">{{record.orderNo}}</el-button></template></ChatProjectActions></div>
    <div class="technical-requirements__tools"><strong>技术需求汇总</strong><small>消息菜单“添加技术需求”逐段加入；可直接编辑</small><el-button size="small" :disabled="!dirty||busy" :loading="busy" @click="save">保存汇总</el-button><template v-if="canEnterDevelopment"><el-button size="small" :disabled="busy||handoffBusy" @click="addToTasks">加至开发任务</el-button><el-button size="small" :disabled="busy||handoffBusy" @click="addToReport">加至工作报告</el-button></template><el-button v-if="error" link @click="reload">重新加载</el-button></div>
    <el-input v-model="content" type="textarea" aria-label="技术需求汇总" :input-style="{height:'4cm',minHeight:'100px'}" maxlength="100000" resize="vertical" :disabled="busy" />
    <small v-if="dirty">汇总有未保存修改</small><small v-if="error" role="alert" class="technical-requirements__error">{{error}}</small>
  </section>
  <DevelopmentReportDialog v-if="reportTaskId" :task-id="reportTaskId" @close="reportTaskId=null" />
  <TaskAllocationViewer v-if="reportAllocationTask" :task="reportAllocationTask" @close="reportAllocationTask=null" @changed="refreshAllocationTask" />
</template>
<script setup>
import {ref,computed,onBeforeUnmount,watch,defineAsyncComponent} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {chatRequest} from '@/api/projectChat'
import {newChatRequestId} from '@/utils/chatTopics'
import {subscribe} from '@/utils/realtimeSocket'
import ChatProjectActions from './ChatProjectActions.vue'
import { useRouter } from 'vue-router'
import { canViewTechnicalDevelopment } from '@/utils/technicalDevelopmentAccess'
import { getRequirementTask } from '@/api/technicalRequirementTasks'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import DevelopmentReportDialog from '@/views/technology/DevelopmentReportDialog.vue'
const router=useRouter(),handoffBusy=ref(false),reportTaskId=ref(null)
const TaskAllocationViewer=defineAsyncComponent(()=>import('@/views/technology/TaskAllocationViewer.vue'))
const reportAllocationTask=ref(null)
async function refreshAllocationTask(){try{const value=await getRequirementTask(props.roomId);reportAllocationTask.value=value.task}catch(e){ElMessage.error(e.detail||e.message||'分工刷新失败，请重新打开')}}
const canEnterDevelopment=computed(()=>canViewTechnicalDevelopment())
async function addToTasks(){
  if(!record.value||handoffBusy.value)return
  handoffBusy.value=true
  try{if(dirty.value&&!await save())return;await router.push({path:'/technology-management/development',query:{technicalRoomId:props.roomId}});useProjectChatDock().minimizeWorkspace()}
  catch(e){ElMessage.error(e.detail||e.message||'无法打开开发任务')}finally{handoffBusy.value=false}
}
async function addToReport(){
  if(!record.value||handoffBusy.value)return
  handoffBusy.value=true
  try{if(dirty.value&&!await save())return;const value=await getRequirementTask(props.roomId);if(!value.task_id){ElMessage.warning('请先点击“加至开发任务”，编辑并保存开发任务后再加至工作报告');return}if(value.task?.has_allocations){const mine=value.task.allocations.find(item=>item.executor_id===localStorage.getItem('user_id'));if(mine)reportTaskId.value=mine.task_id;else reportAllocationTask.value=value.task}else reportTaskId.value=value.task_id}
  catch(e){ElMessage.error(e.detail||e.message||'无法打开工作报告')}finally{handoffBusy.value=false}
}
const props=defineProps({roomId:String,active:Boolean})
const emit=defineEmits(['loaded'])
const record=ref(null),content=ref(''),baseline=ref(''),busy=ref(false),error=ref('')
const dirty=computed(()=>content.value!==baseline.value)
let disposed=false,version=0
const pending=new Map()
function apply(data){record.value=data;content.value=data.requirements||'';baseline.value=content.value;error.value='';emit('loaded',data)}
async function load(force=false){const current=++version;try{const data=await chatRequest(`technical/rooms/${props.roomId}`);if(disposed||current!==version||(!force&&record.value&&dirty.value))return;if(data.enabled)apply(data);else{record.value=null;emit('loaded',null)}}catch(e){if(!disposed&&record.value)error.value=e.message}}
watch(()=>props.roomId,()=>load(),{immediate:true})
async function save(){if(!record.value||!dirty.value)return true;busy.value=true;error.value='';try{apply(await chatRequest(`technical/rooms/${props.roomId}`,{method:'put',data:{content:content.value,revision:record.value.revision}}));return true}catch(e){error.value=e.message;return false}finally{busy.value=false}}
async function append(message){
  if(busy.value)throw Error('正在保存需求，请稍后重试')
  if(dirty.value&&!await save())throw Error(error.value)
  const id=pending.get(message.id)||newChatRequestId();pending.set(message.id,id);busy.value=true
  try{const data=await chatRequest(`technical/rooms/${props.roomId}/append`,{method:'post',data:{messageId:message.id,requestId:id}});apply(data);pending.delete(message.id);ElMessage.success('已添加到技术需求汇总')}
  catch(e){error.value=e.message;throw e}finally{busy.value=false}
}
async function reload(){if(dirty.value){try{await ElMessageBox.confirm('重新加载会替换未保存的汇总修改，是否继续？','重新加载',{type:'warning'})}catch{return}}await load(true)}
const unsubscribe=subscribe('technical_requirements_changed',event=>{if(event.roomId===props.roomId&&props.active&&record.value&&!dirty.value&&!busy.value)load()})
onBeforeUnmount(()=>{disposed=true;version++;unsubscribe()})
defineExpose({append})
</script>
<style scoped>
.technical-requirements{flex:none;max-height:45vh;overflow:auto;padding:10px 14px;background:white;border-bottom:1px solid #e2e8f0}.technical-requirements__heading,.technical-requirements__tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:7px}.technical-requirements__tools small{flex:1;color:#64748b;font-size:11px}.technical-requirements__error{display:block;color:#b91c1c}
</style>
