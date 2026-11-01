<template>
  <DraggableFormDialog :model-value="modelValue" :title="isArrangement?'项目进度':'状态汇报'" width="min(1120px, calc(100vw - 32px))" top="5vh" class="annotation-work-status-dialog" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="done=>{if(!saving)done()}" @update:model-value="$emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="isArrangement?'项目进度':'状态汇报'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
      <template v-if="data.ready">
        <p>{{data.work_date}} · {{isArrangement?'安排状态与预计还需时间会同步到状态汇报。':'显示今日曾调整为“今日进行中”的本人项目；用时填写今日累计值，同一项目的工作报告自动汇总。'}}</p>
        <el-radio-group v-if="!isArrangement" v-model="slot" class="report-slot-tabs" @change="buildEntries">
          <el-radio-button v-for="value in data.available_slots||[]" :key="value" :value="value">{{workSlotLabel(value)}}</el-radio-button>
        </el-radio-group>
        <AppForm ref="form" :model="formModel" label-position="top" :disabled="saving">
          <section v-if="!isArrangement" class="status-project-card">
            <h4>当前空闲状态 · {{workSlotLabel(slot)}}</h4>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="空闲状态" prop="availability.is_idle" :rules="[{validator:(_rule,value,done)=>typeof value==='boolean'?done():done(new Error('请选择是否空闲')),trigger:'change'}]"><el-select v-model="formModel.availability.is_idle" placeholder="请选择是/否" style="width:100%" @change="value=>{if(!value)formModel.availability.expected_idle_time=null}"><el-option :value="true" label="是" /><el-option :value="false" label="否" /></el-select></el-form-item></el-col>
              <el-col v-if="formModel.availability.is_idle" :xs="24" :md="12"><el-form-item label="预计空闲时间" prop="availability.expected_idle_time" :rules="required('请选择预计空闲时间')"><el-select v-model="formModel.availability.expected_idle_time" placeholder="请选择预计空闲时间" clearable style="width:100%"><el-option v-for="option in idleTimeOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select></el-form-item></el-col>
            </el-row>
            <p>预计空闲时间为预估，不计入今日已耗费用时。</p>
            <el-button type="primary" :loading="savingId==='availability'" @click="saveIdle">保存空闲状态</el-button>
          </section>
          <section v-for="(row,index) in formModel.entries" :key="row.id" class="status-project-card" data-dialog-field-search-group :data-dialog-field-search-group-title="`${row.orderNo} ${row.projectName}`">
            <h4>{{row.orderNo}} · {{row.projectName}}</h4>
            <p v-if="row.cumulative_minutes">此前已汇报今日累计用时：{{durationLabel(row.cumulative_minutes)}}</p>
            <template v-if="submitted(row)">
              <el-tag type="success">{{workSlotLabel(slot)}}已提交</el-tag>
              <p class="submitted-note">{{submitted(row).progress_note}}</p>
              <p>今日累计用时：{{durationLabel(submitted(row).cumulative_minutes)}}</p>
            </template>
            <template v-else>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"><el-form-item label="安排状态调整" :prop="`entries.${index}.arrangement_status`" :rules="required('请选择安排状态')"><el-select v-model="row.arrangement_status" style="width:100%"><el-option value="in_progress" label="今日进行中" /><el-option value="not_today" label="今日暂不进行" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="预计还需时间" :prop="`entries.${index}.remaining_time`" :rules="required('请选择预计还需时间')"><el-select v-model="row.remaining_time" placeholder="请选择预计还需时间" clearable style="width:100%"><el-option v-for="option in remainingTimeOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select></el-form-item></el-col>
              </el-row>
              <template v-if="!isArrangement">
                <el-form-item label="今日目前已完成进度" :prop="`entries.${index}.progress_note`" :rules="[{required:true,whitespace:true,message:'请填写今日目前已完成进度',trigger:'blur'}]"><TextInput v-model="row.progress_note" type="textarea" :rows="4" maxlength="1800" show-word-limit placeholder="填写截至现在完成的工作与项目进度" /></el-form-item>
                <el-form-item label="今日已耗费时间（累计）" :prop="`entries.${index}.minutes`" :rules="required('请选择今日累计用时')"><el-select v-model="row.minutes" filterable clearable placeholder="选择截至现在的今日累计用时" style="width:100%"><el-option v-for="minutes in durationOptions" :key="minutes" :value="minutes" :label="durationLabel(minutes)" :disabled="minutes<row.cumulative_minutes" /></el-select></el-form-item>
              </template>
              <el-button :loading="savingId===row.id" :disabled="saving" type="primary" @click="saveOne(row,index)">{{isArrangement?'保存项目进度':'提交本项目汇报'}}</el-button>
              <p v-if="row.error" class="save-error">{{row.error}}</p>
            </template>
            <el-collapse v-if="row.submissions?.length"><el-collapse-item title="查看今日已提交汇报"><div v-for="entry in row.submissions" :key="entry.slot" class="submission-history"><strong>{{workSlotLabel(entry.slot)}} · {{durationLabel(entry.cumulative_minutes)}}（累计）</strong><p class="submitted-note">{{entry.progress_note}}</p></div></el-collapse-item></el-collapse>
          </section>
        </AppForm>
        <el-empty v-if="!formModel.entries.length" :description="isArrangement?'未找到本人负责的项目':'暂无今日进行中的项目，请先在项目的“项目进度”中调整安排状态'" />
      </template>
      <el-alert v-else-if="!loading&&!errorMessage" title="状态汇报功能尚待初始化" type="info" :closable="false" />
    </div>
    <template #footer><el-button :disabled="saving" @click="$emit('update:modelValue',false)">关闭</el-button><el-button :disabled="saving" @click="load(true)">刷新</el-button><el-button v-if="!isArrangement&&formModel.entries.some(row=>!submitted(row))" type="primary" :loading="saving" @click="saveAll">提交全部未汇报项目</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElInput as TextInput} from 'element-plus'
import {getAnnotationWorkStatus,saveAnnotationWorkArrangement,submitAnnotationWorkStatus,saveAnnotationWorkAvailability} from '@/api/projectArrangements'
import {remainingTimeOptions,workSlotLabel} from '@/utils/annotationWorkStatus'
import {durationOptions,durationLabel} from '@/utils/workReportForm'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,request:{type:Object,default:()=>({})}})
defineEmits(['update:modelValue'])
const body=ref(null),form=ref(null),data=ref({}),formModel=reactive({entries:[],availability:{}}),slot=ref('end_shift'),loading=ref(false),saving=ref(false),savingId=ref(''),errorMessage=ref('')
const idleTimeOptions=[{value:'undetermined',label:'未定'},...remainingTimeOptions.slice(0,4)]
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const isArrangement=computed(()=>props.request.mode==='arrangement')
const drafts=new Map()
let timer,controller,requestId=0
const required=message=>[{required:true,message,trigger:'change'}]
const submitted=row=>!isArrangement.value&&row.submissions?.find(entry=>entry.slot===slot.value)
function buildEntries(){
  const availabilityKey=`availability:${slot.value}`
  if(!drafts.has(availabilityKey))drafts.set(availabilityKey,{is_idle:null,expected_idle_time:null,revision:0,...data.value.availability?.[slot.value]})
  formModel.availability=drafts.get(availabilityKey)
  const candidates=(data.value.items||[]).filter(row=>isArrangement.value?row.id===props.request.projectId:!!row.entered_at)
  formModel.entries=candidates.map(row=>{
    const key=`${isArrangement.value?'arrangement':slot.value}:${row.id}`
    if(!drafts.has(key))drafts.set(key,{progress_note:'',minutes:null})
    return Object.assign(drafts.get(key),row,{remaining_time:row.remaining_time||null,error:''})
  })
  nextTick(()=>form.value?.clearValidate())
}
async function load(initial=false){
  controller?.abort();controller=new AbortController();const id=++requestId
  if(initial)loading.value=true
  try{
    const next=await getAnnotationWorkStatus({signal:controller.signal})
    if(id!==requestId)return
    const dayChanged=data.value.work_date&&data.value.work_date!==next.work_date
    if(dayChanged){drafts.clear();slot.value=next.current_slot}
    data.value=next
    if(initial){slot.value=next.available_slots?.includes(props.request.slot)?props.request.slot:next.current_slot||'end_shift';buildEntries()}
    else if(dayChanged)buildEntries()
    // 到达新时点后自动增加标签；不覆盖正在输入的草稿。
  }catch(error){if(id===requestId&&error.code!=='ERR_CANCELED')errorMessage.value=error.detail||'读取状态汇报失败'}
  finally{if(id===requestId)loading.value=false}
}
async function persist(row,index){
  await form.value.validateField([`entries.${index}.arrangement_status`,`entries.${index}.remaining_time`,...(!isArrangement.value?[`entries.${index}.progress_note`,`entries.${index}.minutes`]:[])])
  const values={revision:row.revision,arrangement_status:row.arrangement_status,remaining_time:row.remaining_time}
  savingId.value=row.id
  try{
    const result=isArrangement.value?await saveAnnotationWorkArrangement(row.id,values):await submitAnnotationWorkStatus(row.id,{...values,slot:slot.value,progress_note:row.progress_note,cumulative_minutes:row.minutes})
    Object.assign(row,result,{error:''})
    const original=data.value.items.find(item=>item.id===row.id);if(original)Object.assign(original,result)
    window.dispatchEvent(new CustomEvent('annotation-work-status-updated'))
  }catch(error){row.error=error.detail||'保存失败，请刷新后重试';throw error}
  finally{savingId.value=''}
}
async function persistIdle(){
  await form.value.validateField(['availability.is_idle',...(formModel.availability.is_idle?['availability.expected_idle_time']:[])])
  savingId.value='availability'
  try{
    const result=await saveAnnotationWorkAvailability({slot:slot.value,...formModel.availability})
    Object.assign(formModel.availability,result)
    data.value.availability={...data.value.availability,[slot.value]:result}
  }catch(error){ElMessage.error(error.detail||'保存空闲状态失败');throw error}
  finally{savingId.value=''}
}
async function saveIdle(){if(saving.value)return;saving.value=true;try{await persistIdle();ElMessage.success('空闲状态已保存并同步到工作报告')}catch{}finally{saving.value=false}}
async function saveOne(row,index){if(saving.value)return;saving.value=true;try{if(!isArrangement.value)await persistIdle();await persist(row,index);ElMessage.success(isArrangement.value?'项目进度已更新':'汇报已同步到项目进度与工作报告')}catch(error){if(row.error)ElMessage.error(row.error)}finally{saving.value=false}}
async function saveAll(){
  if(saving.value)return
  try{await form.value.validate()}catch{return}
  saving.value=true;let success=0,failed=0
  try{await persistIdle()}catch{saving.value=false;return}
  for(const [index,row] of formModel.entries.entries()){if(submitted(row))continue;try{await persist(row,index);success++}catch{failed++}}
  saving.value=false
  if(failed)ElMessage.warning(`已提交${success}个项目，${failed}个失败，请查看对应项目提示`)
  else ElMessage.success(`已提交${success}个项目，工作报告用时已更新`)
}
watch(()=>[props.modelValue,props.request],async([visible])=>{clearInterval(timer);controller?.abort();requestId++;if(!visible)return;drafts.clear();data.value={};errorMessage.value='';await load(true);if(props.modelValue)timer=setInterval(()=>{if(!saving.value)load()},30000)},{immediate:true})
onBeforeUnmount(()=>{clearInterval(timer);controller?.abort();requestId++})
</script>
<style>
.annotation-work-status-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.annotation-work-status-dialog .el-dialog__header,.annotation-work-status-dialog .el-dialog__footer{flex-shrink:0}
.annotation-work-status-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.annotation-work-status-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-light);background:var(--el-fill-color-light)}
.annotation-work-status-dialog .status-project-card{border:1px solid var(--el-border-color-light);border-radius:8px;padding:16px;margin:16px 0}
.annotation-work-status-dialog .status-project-card h4{margin:0 0 12px}
.annotation-work-status-dialog .report-slot-tabs{display:flex;flex-wrap:wrap}
.annotation-work-status-dialog .submitted-note{white-space:pre-wrap;overflow-wrap:anywhere}
.annotation-work-status-dialog .submission-history{padding:10px 0;border-bottom:1px solid var(--el-border-color-lighter)}
.annotation-work-status-dialog .save-error{color:var(--el-color-danger)}
</style>
