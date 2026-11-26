<template>
  <DraggableFormDialog v-model="visible" title="新增会议安排" width="min(1100px, calc(100vw - 32px))" top="5vh" class="meeting-form-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="done=>{if(!saving)done()}">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="新增会议安排" placeholder="搜索会议字段" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" v-loading="loading" data-screenshot-editor="own" @submit.prevent="save">
        <div class="meeting-grid">
          <el-form-item label="会议编号"><ReadonlyField model-value="保存后自动生成第N个会议" source="auto" /></el-form-item>
          <el-form-item label="会议类型" prop="meeting_type"><el-select v-model="form.meeting_type" @change="typeChanged"><el-option v-for="type in types" :key="type" :value="type" :label="type" /></el-select></el-form-item>
          <el-form-item label="开始时间（UTC+8）" prop="start"><el-date-picker v-model="form.start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" placeholder="会议开始时间" /></el-form-item>
          <el-form-item label="结束时间（UTC+8）" prop="end"><el-date-picker v-model="form.end" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" placeholder="会议结束时间" /></el-form-item>
          <el-form-item label="会议地点" prop="location"><el-select v-model="form.location"><el-option v-for="place in locations" :key="place" :value="place" :label="place" /></el-select></el-form-item>
          <el-form-item label="提前倒计时"><ReadonlyField :model-value="durationHint" source="auto" /></el-form-item>
          <el-form-item class="meeting-full" label="参与人员" prop="participants">
            <div class="meeting-people">
              <el-checkbox v-model="form.all_people">全体人员（发送时全体在职人员）</el-checkbox>
              <el-select v-model="form.department_ids" multiple filterable clearable :disabled="form.all_people" placeholder="搜索并多选部门，部门内全体人员参加" aria-label="会议参与部门"><el-option v-for="d in directory.departments" :key="d.id" :value="d.id" :label="d.name" /></el-select>
              <el-select v-model="form.user_ids" multiple filterable clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="8" :disabled="form.all_people" placeholder="搜索姓名/账号，单独多选人员" aria-label="会议参与人员">
                <el-option v-for="p in directory.people" :key="p.id" :value="p.id" :label="`${p.name}（${p.username}） · ${availabilityText(p.id)}`"><span>{{p.name}}（{{p.username}}）</span><small :class="{'meeting-conflict':hasConflict(p.id)}"> · {{availabilityText(p.id)}}</small></el-option>
              </el-select>
              <p>已选 {{selectedPeople.length}} 人（部门与人员合并去重）。{{availabilityLoading?'正在核对班次与请假……':availabilityError||'班次和请假仅作参会提醒，不阻止邀请。'}}</p>
              <div class="meeting-selected-people"><el-tag v-for="p in selectedPeople" :key="p.id" :type="hasConflict(p.id)?'warning':'info'">{{p.name}} · {{availabilityText(p.id)}}</el-tag></div>
            </div>
          </el-form-item>
          <template v-if="form.meeting_type==='项目会议'">
            <el-form-item label="项目分类（可不筛选）"><el-select v-model="form.project_type" clearable placeholder="不关联项目" @change="projectTypeChanged"><el-option v-for="type in projectTypes" :key="type" :value="type" :label="type" /></el-select></el-form-item>
            <el-form-item label="关联项目（可不选择）"><el-select v-model="form.project_id" :disabled="!form.project_type" filterable remote clearable :remote-method="searchProjects" :loading="projectLoading" placeholder="搜索订单号、项目名称或客户" @visible-change="value=>value&&searchProjects('')"><el-option v-for="p in projects" :key="p.id" :value="p.id" :label="`${p.order_no} · ${p.project_name}`" /></el-select></el-form-item>
          </template>
          <el-form-item v-if="['部门会议','培训会议'].includes(form.meeting_type)" class="meeting-full" label="会议部门名称"><ReadonlyField :model-value="departmentNames.join('、')||'选择部门或参与人员后自动填入'" source="auto" /></el-form-item>
          <el-form-item v-if="form.meeting_type==='客户会议'" class="meeting-full" label="客户名称" prop="client_ids"><el-select v-model="form.client_ids" multiple filterable remote clearable :remote-method="searchClients" :loading="clientLoading" placeholder="搜索客户全称或简称" @visible-change="value=>value&&searchClients('')"><el-option v-for="c in clients" :key="c.id" :value="c.id" :label="c.name" /></el-select></el-form-item>
          <template v-if="form.meeting_type==='开发会议'">
            <el-form-item label="开发任务名称" prop="task_name"><el-input v-model="form.task_name" maxlength="255" placeholder="填写开发任务名称，可不关联技术开发表单" /></el-form-item>
            <el-form-item label="技术开发表单（可选）"><div><el-select v-if="technicalAccess" v-model="form.technical_task_id" filterable clearable placeholder="选择已有开发任务" @change="technicalSelected"><el-option v-for="task in technicalTasks" :key="task.id" :value="task.id" :label="task.name" /></el-select><el-button v-if="technicalAccess" link type="primary" @click="technicalVisible=true">打开技术开发新增表单</el-button><small v-else>可直接填写任务名称；技术开发表单沿用原有访问权限。</small></div></el-form-item>
          </template>
          <el-form-item class="meeting-full" :label="form.meeting_type==='其他会议'?'其他会议内容（自定义）':'会议主题（可补充）'" prop="topic"><el-input v-model="form.topic" maxlength="500" placeholder="填写会议主题" /></el-form-item>
          <div class="meeting-full meeting-agendas" data-dialog-field-search-label="会议议程">
            <div class="meeting-agenda-title"><strong>会议议程（可多项）</strong><el-button @click="addAgenda">新增议程</el-button></div>
            <div v-for="(agenda,index) in form.agendas" :key="agenda.key" class="meeting-agenda" data-dialog-field-search-group :data-dialog-field-search-group-title="`第${index+1}项议程`">
              <el-form-item :label="`第${index+1}项议程`" :prop="`agendas.${index}.content`" :rules="[{required:true,whitespace:true,message:'请填写议程内容',trigger:'blur'}]"><el-input v-model="agenda.content" type="textarea" :rows="3" maxlength="10000" show-word-limit /></el-form-item>
              <el-checkbox v-model="agenda.same_people">与会议同一批参与人员</el-checkbox>
              <el-form-item v-if="!agenda.same_people" label="本议程参与人员" :prop="`agendas.${index}.user_ids`" :rules="[{type:'array',required:true,min:1,message:'请选择本议程参与人'}]"><el-select v-model="agenda.user_ids" multiple filterable collapse-tags collapse-tags-tooltip placeholder="从会议参与人员中选择"><el-option v-for="p in selectedPeople" :key="p.id" :value="p.id" :label="`${p.name} · ${availabilityText(p.id)}`" /></el-select></el-form-item>
              <el-button link type="danger" @click="removeAgenda(index)">删除议程</el-button>
            </div>
          </div>
          <el-form-item class="meeting-full" label="补充说明 / 线上接入信息" prop="note"><el-input v-model="form.note" type="textarea" :rows="3" maxlength="10000" show-word-limit placeholder="填写补充说明、详细地点或线上会议链接" /></el-form-item>
        </div>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading" @click="save">确认并发送会议安排</el-button></template>
  </DraggableFormDialog>
  <TechnicalDevelopment v-if="technicalVisible" dialog-only :initial-content="form.task_name" @close="technicalVisible=false" @saved="loadTechnical" />
</template>
<script setup>
import {computed,defineAsyncComponent,nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {useFormDraft} from '@/composables/useFormDraft'
import {meetingContext,meetingAvailability,createMeeting,meetingClients,meetingProjects} from '@/api/meetings'
import {getDevelopmentTasks} from '@/api/technicalDevelopment'
import api from '@/api'
import {meetingLeadMinutes,meetingStamp} from '@/utils/meetingTime'
const TechnicalDevelopment=defineAsyncComponent(()=>import('@/views/technology/TechnicalDevelopment.vue'))
const props=defineProps({modelValue:Boolean}),emit=defineEmits(['update:modelValue','saved'])
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const agendaDefault=()=>({key:crypto.randomUUID(),content:'',same_people:true,user_ids:[]})
const defaults=()=>({client_id:crypto.randomUUID(),meeting_type:'项目会议',location:'广州公司内会议室（+线上）',start:'',end:'',all_people:false,department_ids:[],user_ids:[],project_type:'',project_id:'',client_ids:[],technical_task_id:'',task_name:'',topic:'',note:'',agendas:[agendaDefault()]})
const form=reactive(defaults()),formRef=ref(),body=ref(),loading=ref(false),saving=ref(false),error=ref(''),directory=reactive({people:[],departments:[]})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,locateDialogFieldByLabel,clearFieldSearch}=useDialogFieldSearch(body)
const {beginDraft,pauseDraft,clearDraft}=useFormDraft({namespace:'meeting-arrangement',form,formRef,createDefault:defaults})
const types=['项目会议','管理会议','部门会议','培训会议','客户会议','开发会议','其他会议'],locations=['广州公司内会议室（+线上）','广州公司外会议室（+线上）','线上'],projectTypes=['笔译项目','口译项目','标注项目','招聘项目']
const selectedPeople=computed(()=>directory.people.filter(p=>form.all_people||form.user_ids.includes(p.id)||p.department_ids.some(id=>form.department_ids.includes(id))))
const departmentNames=computed(()=>directory.departments.filter(d=>form.department_ids.includes(d.id)||selectedPeople.value.some(p=>p.department_ids.includes(d.id))).map(d=>d.name))
function addAgenda(){if(form.agendas.length>=50){ElMessage.warning('每场会议最多50项议程');return}form.agendas.push(agendaDefault())}
async function removeAgenda(index){try{await ElMessageBox.confirm('确认删除本项议程？','删除议程',{type:'warning'})}catch{return}form.agendas.splice(index,1)}
watch(selectedPeople,people=>{const ids=new Set(people.map(p=>p.id));for(const agenda of form.agendas)agenda.user_ids=agenda.user_ids.filter(id=>ids.has(id))})
const durationHint=computed(()=>{const start=meetingStamp(form.start),end=meetingStamp(form.end);return start&&end&&Date.parse(end)>Date.parse(start)?`会议${(Date.parse(end)-Date.parse(start))/60000}分钟，提前${meetingLeadMinutes(start,end)}分钟显示倒计时`:'选择会议起止时间后计算'})
const rules={meeting_type:[{required:true,message:'请选择会议类型'}],location:[{required:true,message:'请选择地点'}],start:[{required:true,message:'请选择开始时间'}],end:[{required:true,validator:(_r,v,done)=>done(v&&Date.parse(meetingStamp(v))>Date.parse(meetingStamp(form.start))?undefined:new Error('结束时间须晚于开始时间'))}],participants:[{required:true,validator:(_r,_v,done)=>done(selectedPeople.value.length?undefined:new Error('请至少选择一名参会人员'))}],client_ids:[{validator:(_r,v,done)=>done(form.meeting_type!=='客户会议'||v.length?undefined:new Error('请选择客户'))}],task_name:[{validator:(_r,v,done)=>done(form.meeting_type!=='开发会议'||v.trim()?undefined:new Error('请输入开发任务名称'))}],topic:[{validator:(_r,v,done)=>done(form.meeting_type!=='其他会议'||v.trim()?undefined:new Error('请输入其他会议内容'))}]}
const availability=ref({}),availabilityLoading=ref(false),availabilityError=ref('');let availabilityController,availabilityTimer,availabilitySequence=0
function availabilityText(id){if(!form.start||!form.end)return '请先选择会议时间';if(availabilityLoading.value)return '正在核对';const value=availability.value[id];if(!value)return '班次/请假暂未核对';return `${value.in_shift?'在班':'非完整班次内'}：${value.shift}；${value.on_leave?'有请假冲突':'无请假'}`}
const hasConflict=id=>Boolean(availability.value[id]&&(!availability.value[id].in_shift||availability.value[id].on_leave))
async function loadAvailability(){availabilityController?.abort();const id=++availabilitySequence;availability.value={};availabilityError.value='';if(!form.start||!form.end||Date.parse(meetingStamp(form.end))<=Date.parse(meetingStamp(form.start)))return;availabilityController=new AbortController();availabilityLoading.value=true;try{const rows=await meetingAvailability({start_at:meetingStamp(form.start),end_at:meetingStamp(form.end)},availabilityController.signal);if(id===availabilitySequence)availability.value=Object.fromEntries(rows.map(row=>[row.user_id,row]))}catch(e){if(id===availabilitySequence&&e.code!=='ERR_CANCELED')availabilityError.value='班次与请假核对失败，请调整时间重试'}finally{if(id===availabilitySequence)availabilityLoading.value=false}}
watch(()=>[form.start,form.end],()=>{clearTimeout(availabilityTimer);availabilityController?.abort();availabilitySequence++;availabilityLoading.value=false;availability.value={};availabilityTimer=setTimeout(loadAvailability,400)})
const clients=ref([]),projects=ref([]),clientLoading=ref(false),projectLoading=ref(false)
let clientTimer,projectTimer,clientController,projectController,clientSequence=0,projectSequence=0
function searchClients(keyword){clearTimeout(clientTimer);clientController?.abort();const id=++clientSequence;const run=async()=>{clientController=new AbortController();clientLoading.value=true;try{const rows=await meetingClients(keyword,clientController.signal);if(id===clientSequence)clients.value=[...new Map([...clients.value.filter(c=>form.client_ids.includes(c.id)),...rows].map(c=>[c.id,c])).values()]}catch(e){if(e.code!=='ERR_CANCELED')ElMessage.error('客户加载失败，请重新搜索')}finally{if(id===clientSequence)clientLoading.value=false}};if(keyword)clientTimer=setTimeout(run,400);else run()}
function searchProjects(keyword){clearTimeout(projectTimer);projectController?.abort();const id=++projectSequence;if(!form.project_type)return;const run=async()=>{projectController=new AbortController();projectLoading.value=true;try{const result=await meetingProjects(form.project_type,keyword,projectController.signal);if(id===projectSequence)projects.value=[...new Map([...projects.value.filter(p=>p.id===form.project_id),...result.items].map(p=>[p.id,p])).values()]}catch(e){if(e.code!=='ERR_CANCELED')ElMessage.error('项目加载失败，请重新搜索')}finally{if(id===projectSequence)projectLoading.value=false}};if(keyword)projectTimer=setTimeout(run,400);else run()}
function projectTypeChanged(){form.project_id='';projects.value=[];searchProjects('')}
function typeChanged(){formRef.value?.clearValidate()}
const technicalVisible=ref(false),technicalAccess=ref(false),technicalTasks=ref([])
async function loadTechnical(){if(!technicalAccess.value)return;try{const result=await getDevelopmentTasks();technicalTasks.value=Array.isArray(result)?result:result.items||[]}catch{ElMessage.error('技术开发任务加载失败')}}
function technicalSelected(id){const task=technicalTasks.value.find(t=>t.id===id);if(task)form.task_name=task.name.slice(0,255)}
let openSequence=0
watch(visible,async value=>{if(!value){pauseDraft();openSequence++;return}const id=++openSequence;error.value='';loading.value=true;Object.assign(form,defaults());clearFieldSearch();try{const data=await meetingContext();if(id!==openSequence)return;Object.assign(directory,data);await beginDraft('new');searchClients('');if(form.project_type)searchProjects('');await loadAvailability();const access=await api.get('/technical-development/access');if(id===openSequence){technicalAccess.value=access.can_enter;if(access.can_enter)loadTechnical()}}catch(e){if(id===openSequence)error.value=e.detail||'会议目录加载失败，请关闭后重试'}finally{if(id===openSequence)loading.value=false}})
async function save(){if(saving.value||loading.value)return;try{await formRef.value.validate()}catch{return}if(['部门会议','培训会议'].includes(form.meeting_type)&&!departmentNames.value.length){error.value='所选人员未设置部门，请选择部门';await locateDialogFieldByLabel('参与人员');return}saving.value=true;error.value='';try{const payload={...form,start_at:meetingStamp(form.start),end_at:meetingStamp(form.end),project_id:form.project_id||null,technical_task_id:form.technical_task_id||null};delete payload.start;delete payload.end;const meeting=await createMeeting(payload);clearDraft();visible.value=false;emit('saved',meeting);window.dispatchEvent(new Event('meetings-changed'));ElMessage.success('会议安排已发送，请在会议安排中查看回执')}catch(e){error.value=e.detail||'会议发送失败，请重试'}finally{saving.value=false}}
onBeforeUnmount(()=>{openSequence++;clearTimeout(availabilityTimer);clearTimeout(clientTimer);clearTimeout(projectTimer);availabilityController?.abort();clientController?.abort();projectController?.abort()})
</script>
<style scoped>.meeting-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}.meeting-full{grid-column:1/-1}.meeting-people{width:100%;display:flex;flex-direction:column;gap:10px}.meeting-people p{margin:0;color:#64748b}.meeting-selected-people{display:flex;flex-wrap:wrap;gap:6px;max-height:180px;overflow-y:auto}.meeting-grid :deep(.el-select),.meeting-grid :deep(.el-date-editor){width:100%}.meeting-conflict{color:#dc2626}@media(max-width:700px){.meeting-grid{grid-template-columns:1fr}}</style>
<style>.meeting-form-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.meeting-form-dialog .el-dialog__header,.meeting-form-dialog .el-dialog__footer{flex-shrink:0}.meeting-form-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.meeting-form-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>

<style scoped>.meeting-agenda-title{display:flex;align-items:center;justify-content:space-between;margin:12px 0}.meeting-agenda{padding:14px;border:1px solid #dbe3ec;border-radius:6px;margin-bottom:12px}</style>
