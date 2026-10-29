<template>
  <DraggableFormDialog v-model="visible" title="请假" width="min(840px, calc(100vw - 32px))" top="5vh" class="attendance-leave-dialog" :before-close="beforeClose" :close-on-click-modal="false" destroy-on-close>
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="请假" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
      <AppForm data-screenshot-editor="own" ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="开始时间" prop="start_at"><el-date-picker v-model="form.start_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY年MM月DD日 HH:mm" placeholder="选择请假开始时间" :disabled="saving" /></el-form-item>
        <el-form-item label="结束时间" prop="end_at"><el-date-picker v-model="form.end_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY年MM月DD日 HH:mm" placeholder="选择请假结束时间" :disabled="saving" /></el-form-item>
        <el-form-item label="请假原因" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="500" show-word-limit :disabled="saving" /></el-form-item>
      </AppForm>
      <el-alert title="保存后请假立即生效，并向全体在用人员发送会话消息和铃铛通知。请假审批：待开发。时间统一为 UTC+8。" type="info" :closable="false" />
      <div v-loading="previewing" class="attendance-preview"><el-alert v-if="error" :title="error" type="warning" :closable="false" /><template v-if="preview"><p><strong>请假时长：{{durationLabel(preview.minutes)}}</strong></p><p>{{preview.note}}</p><el-table :data="preview.days" border><el-table-column prop="day" label="日期" width="115" /><el-table-column label="本人班次" min-width="200"><template #default="{row}">{{row.shift?`${row.shift.label} · ${row.shift.periods.join(' / ')}`:'休息日或未安排班次'}}</template></el-table-column><el-table-column label="班次内请假" width="135"><template #default="{row}">{{durationLabel(row.minutes)}}</template></el-table-column></el-table></template></div>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="previewing" @click="save">保存并通知全体</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,reactive,watch,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {previewAttendanceLeave,submitAttendanceLeave} from '@/api/attendance'
import {attendanceWindow,durationLabel} from '@/utils/attendance'
const visible=defineModel({type:Boolean,default:false}),emit=defineEmits(['saved'])
const form=reactive({start_at:'',end_at:'',reason:''}),formRef=ref(),body=ref(),preview=ref(null),previewing=ref(false),saving=ref(false),error=ref('')
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const rules={start_at:[{required:true,message:'请选择开始时间',trigger:'change'}],end_at:[{required:true,message:'请选择结束时间',trigger:'change'},{validator:(_rule,value,callback)=>callback(value&&value<=form.start_at?new Error('结束时间必须晚于开始时间'):undefined),trigger:'change'}],reason:[{required:true,whitespace:true,message:'请填写请假原因',trigger:'blur'}]}
let timer,controller,sequence=0,clientId=''
function beforeClose(done){if(!saving.value)done()}
watch(visible,value=>{if(value){Object.assign(form,{start_at:'',end_at:'',reason:''});preview.value=null;error.value='';clientId=crypto.randomUUID();clearFieldSearch()}else{clearTimeout(timer);controller?.abort();sequence++}})
watch(()=>[form.start_at,form.end_at],()=>{clearTimeout(timer);controller?.abort();const id=++sequence;clientId=crypto.randomUUID();preview.value=null;error.value='';previewing.value=false;if(!visible.value||!form.start_at||!form.end_at||form.end_at<=form.start_at)return;timer=setTimeout(async()=>{controller=new AbortController();previewing.value=true;try{const value=await previewAttendanceLeave(attendanceWindow(form),{signal:controller.signal});if(id===sequence)preview.value=value}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取班次失败，请重试'}finally{if(id===sequence)previewing.value=false}},400)})
watch(()=>form.reason,()=>{if(!saving.value)clientId=crypto.randomUUID()})
async function save(){if(saving.value)return;try{await formRef.value.validate()}catch{return}saving.value=true;try{const value=await submitAttendanceLeave({...attendanceWindow(form),reason:form.reason,client_id:clientId});ElMessage.success(value.message);visible.value=false;emit('saved')}catch(e){ElMessage.error(e.detail||'请假保存失败，尚未确认成功，请重试')}finally{saving.value=false}}
onBeforeUnmount(()=>{clearTimeout(timer);controller?.abort();sequence++})
</script>
<style scoped>.attendance-preview{margin-top:16px;font-size:13px;color:#475569}.attendance-preview p{line-height:1.7}.attendance-leave-dialog :deep(.el-date-editor){width:100%}</style>
<style>.attendance-leave-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.attendance-leave-dialog>.el-dialog__header,.attendance-leave-dialog>.el-dialog__footer{flex-shrink:0}.attendance-leave-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.attendance-leave-dialog>.el-dialog__footer{padding:14px 20px;border-top:1px solid #e2e8f0;background:#f8fafc}</style>
