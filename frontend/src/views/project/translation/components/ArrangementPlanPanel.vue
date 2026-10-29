<template>
  <section class="arrangement-plan-panel" v-loading="loading">
    <div class="common-instruction-editor">
      <strong>给被安排人的共同说明</strong>
      <p class="plan-tip">本项目所有被安排人员均可在“今日任务”中查看；下方各人另填具体任务。点击“保存安排”时会一并保存。</p>
      <el-input v-if="canWrite" v-model="instructionDraft" type="textarea" :autosize="{minRows:3,maxRows:8}" :disabled="saving||loading" maxlength="10000" show-word-limit aria-label="项目共同说明" placeholder="填写项目背景、统一要求、注意事项等，所有被安排人员可见" />
      <div v-else class="common-instruction-text">{{data.common_instruction||'未填写共同说明'}}</div>
      <el-button v-if="canWrite" :disabled="saving||loading||instructionDraft===(data.common_instruction||'')" :loading="saving" @click="saveInstruction">保存共同说明</el-button>
    </div>
    <div class="plan-toolbar"><span>最近安排／调整：{{data.updated_by_name||'-'}} · {{formatTime(data.updated_at)}}</span><el-button :disabled="saving" @click="load">刷新</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p v-if="canWrite" class="plan-tip">拖动左侧手柄调整执行顺序，松开后保存；箭头表示先后顺序。</p>
    <div class="plan-current-tasks">
      <template v-for="(task,index) in data.tasks" :key="task.id">
        <div v-if="index" class="execution-down-arrow" aria-hidden="true">↓</div>
        <div class="assignment-line" @dragover.prevent @drop.prevent="dropTask($event,task)">
          <button v-if="canWrite" type="button" class="task-drag-handle" :draggable="!saving" :disabled="saving" :aria-label="`拖动调整${task.assignee_name}的执行顺序`" @dragstart.stop="startDrag($event,task)" @dragend="dragged=''">⠿</button>
          <span class="task-step">{{index+1}}</span><strong>{{task.assignee_name}}</strong>
          <div class="task-description"><el-input v-model="task.content" type="textarea" :autosize="{minRows:1,maxRows:5}" :disabled="!canWrite||saving||task.status==='completed'" maxlength="10000" placeholder="具体任务" /><small>安排人：{{task.assigned_by_name||'-'}} · {{formatTime(task.created_at)}} · 任务日期 {{task.work_date}}</small></div>
          <el-tag>{{statusLabels[task.status]}}</el-tag><el-button v-if="canWrite&&task.status!=='completed'" :loading="saving" @click="saveEdit(task)">保存修改</el-button>
        </div>
      </template>
      <el-empty v-if="!data.tasks.length&&!loading" description="暂无已保存安排" :image-size="50" />
    </div>
    <el-collapse v-model="expanded"><el-collapse-item :title="`安排与调整记录（${data.history_total}）`" name="history">
      <p class="plan-tip">记录每次新增安排、内容修改、顺序调整和任务状态变化。首次快照仅记录当时已有安排。</p>
      <el-collapse>
        <el-collapse-item v-for="event in data.history" :key="event.id" :name="event.id" :title="`第${event.revision}版 · ${operationLabels[event.operation]||event.operation} · ${event.actor_name} · ${formatTime(event.created_at)}`">
          <div class="history-snapshots"><div v-for="(snapshot,key) in {before:event.before_snapshot,after:event.after_snapshot}" :key="key"><strong>{{key==='before'?'调整前':'调整后'}}</strong><p class="common-instruction-text">共同说明：{{snapshot.common_instruction||'未填写'}}</p><ol><li v-for="task in snapshot.tasks||[]" :key="task.id"><strong>{{task.assignee_name}}</strong> · {{task.content}} · {{task.work_date}} · {{statusLabels[task.status]}} · 预计{{task.estimated_minutes}}分钟 / 实际{{task.actual_minutes}}分钟</li></ol><span v-if="!snapshot.tasks?.length">暂无安排</span></div></div>
        </el-collapse-item>
      </el-collapse>
      <el-pagination v-model:current-page="historyPage" :total="data.history_total" :page-size="10" layout="total, prev, pager, next" small @current-change="load" />
    </el-collapse-item></el-collapse>
  </section>
</template>
<script setup>
import {onBeforeUnmount,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getProjectArrangementDetail,reorderProjectArrangements,editArrangementTask,saveProjectArrangementInstruction} from '@/api/projectArrangements'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
const props=defineProps({projectId:{type:String,required:true},canWrite:Boolean,refreshKey:{type:Number,default:0}})
const emit=defineEmits(['changed'])
const data=ref({tasks:[],history:[],history_total:0,revision:0}),loading=ref(false),saving=ref(false),error=ref(''),dragged=ref(''),historyPage=ref(1),expanded=ref([])
const instructionDraft=ref('')
const statusLabels={pending:'待进行',in_progress:'进行中',completed:'已完成'}
const operationLabels={baseline:'已有安排首次快照',assign:'新增安排',edit:'修改任务／状态',reorder:'调整执行顺序',complete:'完成任务并加入工作报告',instruction:'修改共同说明'}
let sequence=0,controller,originalContents=new Map()
function applyData(result){data.value=result;instructionDraft.value=result.common_instruction||'';originalContents=new Map(result.tasks.map(task=>[task.id,task.content]))}
function getInstruction(){return loading.value||saving.value||error.value?null:{common_instruction:instructionDraft.value,instruction_revision:data.value.instruction_revision||0}}
async function saveInstruction(){if(saving.value||loading.value)return;saving.value=true;error.value='';try{applyData(await saveProjectArrangementInstruction(props.projectId,{content:instructionDraft.value,revision:data.value.instruction_revision||0}));historyPage.value=1;emit('changed');ElMessage.success('共同说明已保存，所有被安排人员可查看')}catch(e){error.value=e.detail||'保存共同说明失败，请刷新后重试'}finally{saving.value=false}}
defineExpose({getInstruction})
async function load(){const id=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const result=await getProjectArrangementDetail(props.projectId,{page:historyPage.value},{signal:controller.signal});if(id===sequence)applyData(result)}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取安排失败'}finally{if(id===sequence)loading.value=false}}
function startDrag(event,task){dragged.value=task.id;event.dataTransfer.setData('application/x-arrangement-task',task.id);event.dataTransfer.effectAllowed='move'}
async function dropTask(event,target){
  if(!dragged.value)return
  event.stopPropagation()
  if(!props.canWrite||saving.value||target.id===dragged.value)return
  if(instructionDraft.value!==(data.value.common_instruction||'')){ElMessage.warning('请先保存共同说明，再调整执行顺序');return}
  if(data.value.tasks.some(task=>originalContents.get(task.id)!==task.content)){ElMessage.warning('请先保存任务内容修改，再调整执行顺序');return}
  const ids=data.value.tasks.map(t=>t.id),from=ids.indexOf(dragged.value),to=ids.indexOf(target.id)
  if(from<0||to<0)return
  ids.splice(to,0,...ids.splice(from,1));dragged.value='';saving.value=true;error.value=''
  try{applyData(await reorderProjectArrangements(props.projectId,{revision:data.value.revision,task_ids:ids}));historyPage.value=1;emit('changed');ElMessage.success('执行顺序已保存')}
  catch(e){error.value=e.detail||'排序保存失败，请刷新后重试'}finally{saving.value=false}
}
async function saveEdit(task){if(instructionDraft.value!==(data.value.common_instruction||''))return ElMessage.warning('请先保存共同说明，再修改个人任务');if(!task.content.trim())return ElMessage.warning('请填写具体任务');saving.value=true;try{await editArrangementTask(task.id,{revision:task.revision,content:task.content});await load();emit('changed');ElMessage.success('任务已更新，修改记录已保存')}catch(e){error.value=e.detail||'修改失败，请刷新后重试'}finally{saving.value=false}}
watch(()=>[props.projectId,props.refreshKey],()=>{historyPage.value=1;load()},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
.common-instruction-editor{display:flex;flex-direction:column;gap:8px;margin-bottom:16px;padding:12px;border:1px solid #e2e8f0;border-radius:6px}.common-instruction-editor>.el-button{align-self:flex-end}.common-instruction-text{white-space:pre-wrap;overflow-wrap:anywhere}.common-instruction-editor .plan-tip{margin:0}

.plan-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:12px;color:#64748b}.plan-tip{color:#64748b;font-size:12px}.plan-current-tasks{max-height:560px;overflow-y:auto}.assignment-line{display:flex;gap:10px;align-items:center;padding:10px 4px}.assignment-line>strong{width:85px;flex-shrink:0}.task-description{flex:1;min-width:100px}.task-description small{display:block;color:#64748b;font-size:11px;margin-top:4px}.task-drag-handle{border:0;background:#f1f5f9;color:#475569;cursor:grab;padding:8px;border-radius:4px;font-size:20px}.task-drag-handle:active{cursor:grabbing}.task-step{border-radius:50%;background:#dbeafe;color:#1d4ed8;min-width:24px;text-align:center}.execution-down-arrow{color:#64748b;text-align:center;font-size:22px}.history-snapshots{display:grid;grid-template-columns:1fr 1fr;gap:20px;font-size:12px;overflow-wrap:anywhere}.history-snapshots li{margin:8px 0}.el-pagination{margin-top:12px}@media(max-width:768px){.history-snapshots{grid-template-columns:1fr}.assignment-line{flex-wrap:wrap}.task-description{flex-basis:65%}}
</style>
