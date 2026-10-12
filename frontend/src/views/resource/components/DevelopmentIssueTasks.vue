<template>
  <DraggableFormDialog :z-index="100003" v-model="visible" title="后续安排" width="min(960px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body destroy-on-close>
    <div v-loading="loading">
      <el-button v-if="issue.can_edit" type="primary" @click="editTask()">新增后续任务</el-button>
      <el-empty v-if="!issue.tasks?.length" description="暂无后续安排" />
      <article v-for="task in issue.tasks" :key="task.id" class="issue-task-card">
        <p><strong>{{ task.content }}</strong></p>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="执行人">{{ task.executor_name }}</el-descriptions-item><el-descriptions-item label="实际进度">{{ issueStatusLabel(task.status) }}</el-descriptions-item>
          <el-descriptions-item label="预定完成日期">{{ issueDateLabel(task.planned_date) }}</el-descriptions-item><el-descriptions-item label="实际完成日期">{{ issueDateLabel(task.completed_date) }}</el-descriptions-item>
          <el-descriptions-item label="进展说明" :span="2">{{ task.progress || '-' }}</el-descriptions-item><el-descriptions-item label="备注" :span="2">{{ task.remarks || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="issue-task-actions"><el-button v-if="task.can_update_progress" link type="primary" @click="editTask(task)">{{ task.can_edit ? '编辑任务' : '更新进度' }}</el-button><el-button v-if="task.can_edit" link type="danger" :disabled="removing" @click="remove(task)">删除任务</el-button></div>
      </article>
    </div>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog :z-index="100004" v-model="editing" :title="form.id ? '编辑后续任务' : '新增后续任务'" width="min(960px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="form.id ? '编辑后续任务' : '新增后续任务'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <el-alert v-if="conflict" title="任务已被其他人修改，当前草稿已保留。请先复制需要保留的内容，或重新加载后编辑。" type="warning" :closable="false"><el-button text @click="reloadDraft">重新加载</el-button></el-alert>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="issue-grid">
          <el-form-item label="安排内容" prop="content" class="wide"><el-input v-if="canManage" v-model="form.content" type="textarea" :autosize="{minRows:4,maxRows:10}" maxlength="10000" /><ReadonlyField v-else :model-value="form.content" type="textarea" source="auto" /><span v-if="!canManage" class="issue-hint">任务内容由提出人、收录人或统筹人员维护</span></el-form-item>
          <el-form-item label="执行人" prop="executor_id"><el-select popper-class="chat-topic-select-popper" v-if="canManage" v-model="form.executor_id" filterable placeholder="选择执行人"><el-option v-for="person in people" :key="person.id" :value="person.id" :label="person.name" /></el-select><ReadonlyField v-else :model-value="form.executor_name" source="auto" /></el-form-item>
          <el-form-item label="预定完成日期" prop="planned_date"><el-date-picker popper-class="chat-topic-select-popper" v-if="canManage" v-model="form.planned_date" type="date" value-format="YYYY-MM-DD" clearable /><ReadonlyField v-else :model-value="issueDateLabel(form.planned_date)" source="auto" /></el-form-item>
          <el-form-item label="实际进度" prop="status"><el-select popper-class="chat-topic-select-popper" v-model="form.status" @change="statusChanged"><el-option v-for="status in issueStatuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item>
          <el-form-item v-if="form.status === 'completed'" label="实际完成日期" prop="completed_date"><el-date-picker popper-class="chat-topic-select-popper" v-model="form.completed_date" type="date" value-format="YYYY-MM-DD" :disabled-date="futureDate" /></el-form-item>
          <el-form-item label="进展说明" prop="progress" class="wide"><el-input v-model="form.progress" type="textarea" :autosize="{minRows:4,maxRows:10}" maxlength="10000" /></el-form-item>
          <el-form-item label="备注" prop="remarks" class="wide"><el-input v-if="canManage" v-model="form.remarks" type="textarea" :autosize="{minRows:3,maxRows:8}" maxlength="10000" /><ReadonlyField v-else :model-value="form.remarks || '-'" source="auto" type="textarea" /></el-form-item>
        </div>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="beforeClose(() => editing = false)">取消</el-button><el-button type="primary" :loading="saving" :disabled="conflict" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { issueApi } from '@/api/resourceIssues'
import { hongKongToday, issueStatuses, issueStatusLabel, issueDateLabel } from '@/utils/resourceIssues'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import './issueDialogs.css'
const emit = defineEmits(['saved'])
const visible=ref(false), editing=ref(false), loading=ref(false), saving=ref(false), removing=ref(false), conflict=ref(false), bodyRef=ref(), formRef=ref(), people=ref([])
const issue=reactive({}), form=reactive({}), canManage=computed(() => !!issue.can_edit)
const rules=computed(() => ({
  ...(canManage.value ? {content:[{required:true,whitespace:true,message:'请填写安排内容',trigger:'blur'}],executor_id:[{required:true,message:'请选择执行人',trigger:'change'}]} : {}),
  status:[{required:true,message:'请选择实际进度',trigger:'change'}],
  ...(form.status === 'completed' ? {completed_date:[{required:true,message:'请选择实际完成日期',trigger:'change'},{validator:(_r,value,done)=>value>hongKongToday()?done(new Error('实际完成日期不能晚于香港时间当天')):done(),trigger:'change'}]} : {}),
}))
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(bodyRef)
let baseline=''
const draft=()=>JSON.stringify(form)
async function open(row) {
  visible.value=true; loading.value=true
  try { const [data,options]=await Promise.all([issueApi.detail(row.id),issueApi.options()]); Object.assign(issue,data);people.value=options.users }
  catch(e){visible.value=false;ElMessage.error(e.message)} finally{loading.value=false}
}
async function editTask(task) {
  Object.keys(form).forEach(key=>delete form[key]);Object.assign(form,task?{...task}:{content:'',executor_id:'',planned_date:null,status:'pending',progress:'',completed_date:null,remarks:''})
  conflict.value=false;clearFieldSearch();editing.value=true;baseline=draft();await nextTick();formRef.value?.clearValidate()
}
function statusChanged(){form.completed_date=form.status==='completed'?(form.completed_date||hongKongToday()):null;formRef.value?.clearValidate('completed_date')}
// 日期面板中的候选值代表用户选择的纯日期，不能再按浏览器时区换算。
function futureDate(value){const date=`${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;return date>hongKongToday()}
async function beforeClose(done){if(saving.value)return;if(draft()!==baseline){try{await ElMessageBox.confirm('当前任务修改尚未保存，是否放弃？','关闭任务',{type:'warning',customClass:'chat-issue-message-box',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}done()}
function changed(data){Object.assign(issue,data);emit('saved',data)}
async function save(){
  if(saving.value||conflict.value||!await formRef.value.validate().catch(()=>false))return
  saving.value=true
  try{
    const payload={revision:issue.revision,status:form.status,progress:form.progress,completed_date:form.completed_date||null}
    if(canManage.value)Object.assign(payload,{content:form.content,executor_id:form.executor_id,planned_date:form.planned_date||null,remarks:form.remarks})
    changed(await issueApi.saveTask(issue.id,payload,form.id));editing.value=false;ElMessage.success('后续任务已保存')
  }catch(e){conflict.value=e.status===409||e.response?.status===409;ElMessage.error(e.message)}finally{saving.value=false}
}
async function reloadDraft(){
  try{await ElMessageBox.confirm('重新加载会替换当前任务草稿，是否继续？','重新加载',{type:'warning',customClass:'chat-issue-message-box'})}catch{return}
  try{const id=form.id;changed(await issueApi.detail(issue.id));const task=issue.tasks.find(t=>t.id===id);if(id&&!task){editing.value=false;ElMessage.warning('任务已被删除');return}await editTask(task)}catch(e){ElMessage.error(e.message)}
}
async function remove(task){
  try{await ElMessageBox.confirm('确定删除这条后续任务吗？删除后无法恢复。','删除任务',{type:'warning',customClass:'chat-issue-message-box'})}catch{return}
  removing.value=true;try{changed(await issueApi.removeTask(issue.id,task.id,issue.revision));ElMessage.success('任务已删除')}catch(e){ElMessage.error(e.message);if(e.status===409||e.response?.status===409)changed(await issueApi.detail(issue.id))}finally{removing.value=false}
}
defineExpose({open})
</script>
<style scoped>.issue-task-actions{display:flex;gap:12px;margin-top:12px}</style>
