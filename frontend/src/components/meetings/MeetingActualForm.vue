<template>
  <DraggableFormDialog v-model="visible" title="确认实际会议时间与参与人员" width="min(840px, calc(100vw - 32px))" top="5vh" append-to-body class="meeting-form-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="done=>{if(!saving)done()}">
    <el-alert title="确认后将按实际耗时，为选中的参与人员各追加一条工作报告。已确认的报告也会追加并同步查看人；报告中的会议记录允许删除，不会重复生成。" type="info" :closable="false" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="正式开始时间（UTC+8）" prop="start"><el-date-picker v-model="form.start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" /></el-form-item>
      <el-form-item label="正式结束时间（UTC+8）" prop="end"><el-date-picker v-model="form.end" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" /></el-form-item>
      <el-form-item label="实际参与人员（可剔除未到人员）" prop="user_ids"><el-select v-model="form.user_ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="10"><el-option v-for="p in meeting.participants" :key="p.user_id" :value="p.user_id" :label="`${p.name} · ${p.response==='declined'?'回执不能参加':p.response==='pending'?'尚未回执':'可以参加'}`" /></el-select></el-form-item>
      <p>回执不能参加的人员默认不选，仍可在下拉列表中手动选回；尚未回执的人员默认保留，请按实际出席情况核对。</p>
      <p>报告具体任务将填写“{{meeting.organizer_name}}召开的会议”及本人参与的议程；工作量为1，单位为次。</p>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">确认并填入工作报告</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import {businessDateTimeInputValue} from '@/utils/dateTime'
import {meetingStamp} from '@/utils/meetingTime'
import {confirmMeetingActual} from '@/api/meetings'
const props=defineProps({modelValue:Boolean,meeting:{type:Object,required:true}}),emit=defineEmits(['update:modelValue','saved'])
const visible=computed({get:()=>props.modelValue,set:v=>emit('update:modelValue',v)})
const form=reactive({start:'',end:'',user_ids:[]}),formRef=ref(),saving=ref(false),error=ref('')
const rules={start:[{required:true,message:'请填写正式开始时间'}],end:[{required:true,validator:(_r,v,done)=>done(v&&Date.parse(meetingStamp(v))>Date.parse(meetingStamp(form.start))?undefined:new Error('结束时间须晚于开始时间'))}],user_ids:[{required:true,type:'array',min:1,message:'请至少选择一名实际参会人员'}]}
watch(visible,value=>{if(value){Object.assign(form,{start:businessDateTimeInputValue(props.meeting.start_at).replace(' ','T'),end:businessDateTimeInputValue(props.meeting.end_at).replace(' ','T'),user_ids:props.meeting.participants.filter(p=>p.response!=='declined').map(p=>p.user_id)});error.value=''}})
async function save(){if(saving.value)return;try{await formRef.value.validate()}catch{return}saving.value=true;try{const result=await confirmMeetingActual(props.meeting.id,{start_at:meetingStamp(form.start),end_at:meetingStamp(form.end),user_ids:form.user_ids});ElMessage.success(result.already_confirmed?'该会议已确认，未重复填报':`已为${result.written_count}人填入${result.duration_minutes}分钟工作报告`);visible.value=false;emit('saved');window.dispatchEvent(new Event('meetings-changed'))}catch(e){error.value=e.detail||'确认失败，请重试'}finally{saving.value=false}}
</script>
