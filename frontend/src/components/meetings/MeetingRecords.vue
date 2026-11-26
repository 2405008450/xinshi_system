<template>
  <section class="meeting-records" data-auto-draft="off">
    <h4>会议记录</h4>
    <template v-if="meeting.is_organizer">
      <el-input v-model="form.content" type="textarea" :rows="5" maxlength="30000" show-word-limit placeholder="填写会议记录。可以只记内容，不安排任务。" aria-label="会议记录内容" />
      <div class="record-actions"><el-button @click="add">新增任务安排</el-button><span>可给多人安排；不新增任务时仅保存会议记录。</span></div>
      <AppForm ref="formRef" :model="form" label-position="top">
        <div v-for="(action,index) in form.actions" :key="action.client_id" class="record-task" data-dialog-field-search-group :data-dialog-field-search-group-title="`任务安排${index+1}`">
          <strong>任务安排{{index+1}}</strong>
          <el-form-item label="执行人（可多选）" :prop="`actions.${index}.user_ids`" :rules="[{type:'array',required:true,min:1,message:'请选择执行人'}]"><el-select v-model="action.user_ids" multiple filterable collapse-tags collapse-tags-tooltip><el-option v-for="p in people" :key="p.id" :value="p.id" :label="`${p.name}（${p.username}）`" /></el-select></el-form-item>
          <el-form-item label="任务类别"><el-radio-group v-model="action.category"><el-radio value="project">项目任务</el-radio><el-radio value="non_project">非项目任务</el-radio></el-radio-group></el-form-item>
          <template v-if="action.category==='project'"><el-form-item label="项目分类" :prop="`actions.${index}.project_type`" :rules="[{required:true,message:'请选择项目分类'}]"><el-select v-model="action.project_type" @change="action.project_id='';action.project_label='' "><el-option v-for="type in projectTypes" :key="type" :value="type" :label="type" /></el-select></el-form-item><el-form-item label="关联项目" :prop="`actions.${index}.project_id`" :rules="[{required:true,message:'请选择项目'}]"><MeetingProjectSelect :project-type="action.project_type" :project-id="action.project_id" :label="action.project_label" @selected="project=>Object.assign(action,{project_id:project?.id||'',project_label:project?`${project.order_no} · ${project.project_name}`:''})" /></el-form-item></template>
          <el-form-item label="具体任务" :prop="`actions.${index}.content`" :rules="[{required:true,whitespace:true,message:'请填写具体任务'}]"><el-input v-model="action.content" type="textarea" :rows="3" maxlength="10000" /></el-form-item>
          <el-form-item label="完成时间（UTC+8）" :prop="`actions.${index}.due`" :rules="[{required:true,message:'请选择完成时间'}]"><el-date-picker v-model="action.due" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-button type="danger" link @click="remove(index)">删除此项未发送安排</el-button>
        </div>
      </AppForm>
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <el-button type="primary" :loading="saving" @click="save">保存会议记录{{form.actions.length?'并发送任务安排':''}}</el-button>
    </template>
    <p v-else class="record-text">{{meeting.record_content||'暂无会议记录'}}</p>
    <h4>已安排任务</h4>
    <el-table :data="meeting.actions||[]" border size="small" max-height="320"><el-table-column prop="assignee_name" label="执行人" width="100" /><el-table-column label="类别" width="100"><template #default="{row}">{{row.category==='project'?'项目任务':'非项目任务'}}</template></el-table-column><el-table-column prop="content" label="具体任务" min-width="240" show-overflow-tooltip /><el-table-column label="完成时间" min-width="180"><template #default="{row}">{{formatBusinessDateTime(row.due_at)}}</template></el-table-column><el-table-column prop="arranger_name" label="安排人" width="100" /><el-table-column label="安排时间" min-width="180"><template #default="{row}">{{formatBusinessDateTime(row.assigned_at)}}</template></el-table-column></el-table>
  </section>
</template>
<script setup>
import {onMounted,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import MeetingProjectSelect from './MeetingProjectSelect.vue'
import {useFormDraft} from '@/composables/useFormDraft'
import {saveMeetingRecord,meetingContext} from '@/api/meetings'
import {meetingStamp} from '@/utils/meetingTime'
import {formatBusinessDateTime} from '@/utils/dateTime'
const props=defineProps({meeting:{type:Object,required:true}}),emit=defineEmits(['saved'])
const people=ref([])
onMounted(async()=>{try{people.value=(await meetingContext()).people}catch{ElMessage.error('任务执行人加载失败，请关闭会议后重试')}})
const form=reactive({content:'',version:0,actions:[]}),formRef=ref(),saving=ref(false),error=ref('')
const {beginDraft,pauseDraft,clearDraft}=useFormDraft({namespace:'meeting-record',form,formRef,createDefault:()=>({content:'',version:0,actions:[]})})
watch(()=>props.meeting.id,async id=>{pauseDraft();Object.assign(form,{content:props.meeting.record_content||'',version:props.meeting.record_version||0,actions:[]});if(props.meeting.is_organizer)await beginDraft(id)},{immediate:true})
const projectTypes=['笔译项目','口译项目','标注项目','招聘项目']
function add(){form.actions.push({client_id:crypto.randomUUID(),user_ids:[],category:'non_project',project_type:'',project_id:'',project_label:'',content:'',due:''})}
async function remove(index){try{await ElMessageBox.confirm('确认删除这项尚未发送的任务安排？','删除任务安排',{type:'warning'})}catch{return}form.actions.splice(index,1)}
async function save(){if(saving.value)return;try{await formRef.value.validate()}catch{return}saving.value=true;error.value='';try{const result=await saveMeetingRecord(props.meeting.id,{content:form.content,version:form.version,actions:form.actions.map(action=>({...action,project_id:action.project_id||null,due_at:meetingStamp(action.due)}))});clearDraft();form.version=result.version;form.actions=[];await beginDraft(props.meeting.id);ElMessage.success('会议记录及任务安排已保存');emit('saved');window.dispatchEvent(new Event('meeting-tasks-changed'))}catch(e){error.value=e.detail||'保存失败，草稿保留，请重试'}finally{saving.value=false}}
defineExpose({save,saving})
</script>
<style scoped>.record-actions{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:12px 0}.record-actions span{color:#64748b}.record-task{padding:14px;margin-bottom:12px;border:1px solid #dbe3ec;border-radius:6px}.record-task :deep(.el-select),.record-task :deep(.el-date-editor){width:100%}.record-text{white-space:pre-wrap}.meeting-records{border-top:1px solid #e2e8f0;margin-top:18px;padding-top:8px}</style>
