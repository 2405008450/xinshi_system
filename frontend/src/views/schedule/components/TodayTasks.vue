<template>
  <section class="today-tasks">
    <div class="today-header"><h3>{{review?'查看任务':'今日任务'}}</h3><div><el-button v-if="!review" type="primary" @click="openPersonal()">自行填写任务</el-button><el-button :loading="loading" @click="query">刷新</el-button></div></div>
    <ArrangementDateFilter v-model="dateRange" />
    <div v-if="review" class="task-filters">
      <el-select v-model="departmentId" clearable filterable placeholder="按部门筛选" @change="query"><el-option v-for="d in directory.departments" :key="d.id" :value="d.id" :label="d.name" /></el-select>
      <el-select v-model="personId" clearable filterable placeholder="按人员筛选" @change="query"><el-option v-for="p in filteredPeople" :key="p.id" :value="p.id" :label="`${p.name}（${p.username}）`" /></el-select>
    </div>
    <el-alert v-if="!ready" title="项目安排任务尚待数据库初始化" type="info" :closable="false" />
    <p class="task-hint">{{dateRange?'按安排日期查看历史任务，含已完成任务。':'显示所选日期任务及此前未完成任务；也可自行填写。'}}用时与工作报告保持一致。</p>
    <el-table :data="rows" v-loading="loading" border row-key="id">
      <el-table-column type="index" label="序号" width="55" />
      <el-table-column v-if="review" prop="assignee_name" label="人员" width="105" />
      <el-table-column prop="order_no" label="订单号" width="150" />
      <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="共同说明" min-width="220"><template #default="{row}"><el-popover v-if="row.common_instruction" trigger="click" placement="left" :width="560" title="项目共同说明" popper-class="task-common-instruction-popover"><div class="task-common-instruction-content">{{row.common_instruction}}</div><template #reference><el-button link type="primary" class="common-instruction-preview">{{row.common_instruction}}</el-button></template></el-popover><span v-else>-</span></template></el-table-column>
      <el-table-column prop="content" label="具体任务" min-width="240" show-overflow-tooltip />
      <el-table-column label="执行顺序" min-width="280"><template #default="{row}"><ExecutionSequence :sequence="row.execution_sequence||[]" :current-id="row.id" /></template></el-table-column>
      <el-table-column prop="work_date" label="安排日期" width="115" />
      <el-table-column label="预计需要时间" width="155"><template #default="{row}"><el-select v-if="!review&&row.status!=='completed'" :model-value="row.estimated_minutes" @change="save(row,{estimated_minutes:$event})"><el-option :value="0" label="未填写" /><el-option v-for="n in durationOptions" :key="n" :value="n" :label="durationLabel(n)" /></el-select><span v-else>{{durationLabel(row.estimated_minutes)}}</span></template></el-table-column>
      <el-table-column label="实际花费时间" width="155"><template #default="{row}"><el-select v-if="!review&&row.status!=='completed'" :model-value="row.actual_minutes" @change="save(row,{actual_minutes:$event})"><el-option :value="0" label="未填写" /><el-option v-for="n in durationOptions" :key="n" :value="n" :label="durationLabel(n)" /></el-select><span v-else>{{durationLabel(row.actual_minutes)}}</span></template></el-table-column>
      <el-table-column label="任务状态" width="140" fixed="right"><template #default="{row}"><el-select v-if="!review&&row.status!=='completed'" :disabled="saving" :model-value="row.status" @change="statusChange(row,$event)"><el-option v-for="(label,key) in labels" :key="key" :value="key" :label="label" /></el-select><el-tag v-else>{{labels[row.status]}}</el-tag></template></el-table-column>
      <el-table-column v-if="!review" label="编辑" width="95" fixed="right"><template #default="{row}"><el-button v-if="row.source==='personal'&&row.status!=='completed'" type="primary" link @click="openPersonal(row)">编辑任务</el-button><span v-else>-</span></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <DraggableFormDialog v-model="personalVisible" :title="personalTarget?'编辑自主任务':'自行填写今日任务'" width="min(1440px, calc(100vw - 32px))" top="5vh" class="task-report-dialog" append-to-body :close-on-click-modal="false" :before-close="done=>{if(!saving)done()}">
      <template #header><DialogFieldSearchHeader ref="personalFieldSearchRef" v-model="personalFieldSearchKeyword" :title="personalTarget?'编辑自主任务':'自行填写今日任务'" :fetch-suggestions="fetchPersonalFieldSuggestions" @select="locatePersonalField" @clear="clearPersonalFieldSearch" /></template>
      <div ref="personalBody">
      <div data-dialog-field-search-label="安排日期"><span>安排日期：</span>
      <el-date-picker v-model="personalDate" type="date" value-format="YYYY-MM-DD" aria-label="自主任务安排日期" :clearable="false" />
      </div>
      <DailyReportEditor ref="personalEditor" planning :single-task="!!personalTarget" :rows="personalRows" :editable="!saving" :categories="context.work_categories" :history="context.task_history||[]" :can-add-project-category="context.can_add_project_category" :category-storage-ready="context.category_storage_ready" @categories-change="Object.assign(context,$event)" />
      </div>
      <template #footer><el-button :disabled="saving" @click="personalVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePersonal">保存任务</el-button></template>
    </DraggableFormDialog>
    <DraggableFormDialog v-model="completionVisible" title="加入工作报告" width="min(1440px, calc(100vw - 32px))" top="5vh" class="task-report-dialog" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="done=>{if(!saving)done()}">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="加入工作报告" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editorBody">
      <p>填写完整工作报告后，保存并将任务标记为已完成。订单号、项目名称、具体任务和实际用时已带入。</p>
      <DailyReportEditor ref="editor" single-task :rows="reportRows" :editable="!saving" :categories="context.work_categories" :history="context.task_history||[]" :can-add-project-category="context.can_add_project_category" :category-storage-ready="context.category_storage_ready" @categories-change="Object.assign(context,$event)" />
      </div>
      <template #footer><el-button :disabled="saving" @click="completionVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="complete">保存报告并完成任务</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getArrangementTasks,getTaskReviewDirectory,editArrangementTask,completeArrangementTask,createPersonalTasks,editPersonalTask,updatePersonalTask,completePersonalTask} from '@/api/projectArrangements'
import {getDailyReportEditorContext} from '@/api/tasks'
import {durationOptions,durationLabel,reportBusinessDate,newReportRow} from '@/utils/workReportForm'
import ArrangementDateFilter from '@/components/common/ArrangementDateFilter.vue'
import DailyReportEditor from './DailyReportEditor.vue'
import ExecutionSequence from '@/components/common/ExecutionSequence.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({review:Boolean,day:{type:String,default:''}})
const rows=ref([]),total=ref(0),page=ref(1),loading=ref(false),saving=ref(false),ready=ref(true),departmentId=ref(''),personId=ref(''),directory=ref({people:[],departments:[]})
const completionVisible=ref(false),selected=ref(null),editor=ref(),reportRows=ref([]),context=ref({})
const dateRange=ref(null),personalVisible=ref(false),personalTarget=ref(null),personalRows=ref([]),personalEditor=ref(),personalDate=ref(reportBusinessDate())
const personalBody=ref(null)
const {fieldSearchRef:personalFieldSearchRef,fieldSearchKeyword:personalFieldSearchKeyword,fetchFieldSuggestions:fetchPersonalFieldSuggestions,locateDialogField:locatePersonalField,locateDialogFieldByLabel:locatePersonalByLabel,clearFieldSearch:clearPersonalFieldSearch}=useDialogFieldSearch(personalBody)
const editorBody=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
const labels={pending:'待进行',in_progress:'进行中',completed:'已完成'}
const filteredPeople=computed(()=>directory.value.people.filter(p=>!departmentId.value||p.departments.some(d=>d.id===departmentId.value)))
let requestId=0,controller
async function load(){controller?.abort();controller=new AbortController();const id=++requestId;loading.value=true;try{const data=await getArrangementTasks({day:props.day||reportBusinessDate(),date_from:dateRange.value?.[0],date_to:dateRange.value?.[1],review:props.review,department_id:departmentId.value||undefined,person_id:personId.value||undefined,page:page.value},{signal:controller.signal});if(id!==requestId)return;rows.value=data.items;total.value=data.total;ready.value=data.ready}catch(error){if(id===requestId&&error.code!=='ERR_CANCELED')ElMessage.error(error.detail||'读取今日任务失败')}finally{if(id===requestId)loading.value=false}}
function query(){page.value=1;load()}
async function save(row,values){if(saving.value)return;saving.value=true;try{Object.assign(row,await (row.source==='personal'?editPersonalTask:editArrangementTask)(row.id,{revision:row.revision,...values}))}catch(error){ElMessage.error(error.detail||'保存任务失败');await load()}finally{saving.value=false}}
async function statusChange(row,status){if(status!=='completed')return save(row,{status});try{context.value=await getDailyReportEditorContext();selected.value={...row};const personal=row.source==='personal';reportRows.value=[{...(personal?row.report_row:{}),source_type:'manual',source_id:row.id,task_type:personal?row.report_row.task_type:'项目工作',task_name:row.project_name,progress_content:row.content,duration_minutes:row.actual_minutes,display_metadata:personal?{...row.report_row.display_metadata}:{report_types:['笔译项目'],order_no:row.order_no,quantity:'',quantity_unit:''}}];completionVisible.value=true}catch(error){ElMessage.error(error.detail||'读取工作报告表单失败')}}
async function complete(){if(saving.value)return;try{await editor.value.validate()}catch{return}saving.value=true;try{await (selected.value.source==='personal'?completePersonalTask:completeArrangementTask)(selected.value.id,{revision:selected.value.revision,item:editor.value.getRows()[0]});completionVisible.value=false;await load();ElMessage.success('已加入工作报告，任务已完成')}catch(error){ElMessage.error(error.detail||'保存失败，任务尚未完成')}finally{saving.value=false}}
async function openPersonal(row=null){try{context.value=await getDailyReportEditorContext();personalTarget.value=row;personalDate.value=row?.work_date||props.day||reportBusinessDate();personalRows.value=[row?{...row.report_row,source_type:'manual',duration_minutes:row.estimated_minutes}:newReportRow()];personalVisible.value=true}catch(e){ElMessage.error(e.detail||'读取任务表单失败')}}
async function savePersonal(){if(saving.value)return;try{await personalEditor.value.validate()}catch{return}if(!personalDate.value){ElMessage.warning('请选择安排日期');await locatePersonalByLabel('安排日期');return}saving.value=true;try{const items=personalEditor.value.getRows();if(!items.length){ElMessage.warning('请至少新增一行任务');return}if(items.length>100){ElMessage.warning('每次最多保存100行任务');return}if(personalTarget.value)await updatePersonalTask(personalTarget.value.id,{work_date:personalDate.value,item:items[0],revision:personalTarget.value.revision});else await createPersonalTasks({work_date:personalDate.value,items});personalVisible.value=false;await load();ElMessage.success('自主任务已保存')}catch(e){ElMessage.error(e.detail||'保存任务失败')}finally{saving.value=false}}
watch(()=>props.day,()=>{dateRange.value=null;query()})
watch(dateRange,query)
watch(departmentId,()=>{if(personId.value&&!filteredPeople.value.some(p=>p.id===personId.value))personId.value=''})
onMounted(async()=>{if(props.review){try{directory.value=await getTaskReviewDirectory()}catch(error){ElMessage.error(error.detail||'读取查看范围失败')}}await load();window.addEventListener('focus',query)})
onBeforeUnmount(()=>{controller?.abort();requestId++;window.removeEventListener('focus',query)})
</script>
<style scoped>
.common-instruction-preview{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}

.today-tasks{padding:14px;border:1px solid #dbe3ec;border-radius:8px;margin-bottom:16px}.today-header{display:flex;justify-content:space-between;align-items:center}.today-header h3{margin:0}.task-filters{display:flex;gap:12px;margin:12px 0}.task-filters .el-select{max-width:240px}.task-hint{font-size:12px;color:#64748b}.el-pagination{margin-top:12px;justify-content:flex-end;overflow-x:auto}
</style>
<style>
.task-common-instruction-popover{max-width:calc(100vw - 32px)!important}.task-common-instruction-content{white-space:pre-wrap;overflow-wrap:anywhere;max-height:360px;overflow-y:auto}

.task-report-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.task-report-dialog .el-dialog__header,.task-report-dialog .el-dialog__footer{flex-shrink:0}.task-report-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.task-report-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}.task-report-dialog .report-editor__scroll{max-height:none;overflow-y:visible}
</style>
