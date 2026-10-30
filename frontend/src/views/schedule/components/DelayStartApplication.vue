<template>
  <el-button @click="open">延迟上班申请</el-button>
  <DraggableFormDialog v-model="visible" title="延迟上班申请" class="delay-start-dialog" append-to-body width="min(760px, calc(100vw - 32px))" top="5vh" :before-close="close" :close-on-click-modal="false">
    <AppForm ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item label="预计上班时间（UTC+8）" prop="requested_start"><el-date-picker v-model="form.requested_start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY年MM月DD日 HH:mm" :disabled="saving" style="width:100%" /></el-form-item><el-form-item label="申请事由" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="1000" show-word-limit :disabled="saving" /></el-form-item></AppForm>
    <el-alert title="提交后通知全体在用人员，并保留申请记录。手机和电脑均可操作。审批待开发，申请不会自动免迟到或调整班次；仍按预定上班时间及15分钟宽限计算。" type="info" :closable="false" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <h4>我的最近申请</h4><el-table :data="items" border max-height="220"><el-table-column label="预计上班" min-width="175"><template #default="{row}">{{formatBusinessDateTime(row.requested_start)}}</template></el-table-column><el-table-column prop="reason" label="事由" min-width="160" show-overflow-tooltip /><el-table-column label="申请时间" min-width="175"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column></el-table>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">提交并通知全体</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {reactive,ref} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {getDelayStartApplications,applyDelayStart} from '@/api/attendance'
import {formatBusinessDateTime,businessDateTimeInputValue} from '@/utils/dateTime'
const emit=defineEmits(['saved']),visible=ref(false),saving=ref(false),error=ref(''),items=ref([]),formRef=ref()
const form=reactive({id:'delay-start-application',client_id:'',requested_start:'',reason:''})
const rules={requested_start:[{required:true,message:'请选择预计上班时间',trigger:'change'}],reason:[{required:true,whitespace:true,message:'请填写申请事由',trigger:'blur'}]}
async function open(){Object.assign(form,{client_id:crypto.randomUUID(),requested_start:businessDateTimeInputValue(new Date()),reason:''});error.value='';visible.value=true;try{const data=await getDelayStartApplications();items.value=data.items}catch(e){error.value=e.detail||'读取申请记录失败'}}
function close(done){if(!saving.value)done()}
async function submit(){if(saving.value||!await formRef.value.validate().catch(()=>false))return;saving.value=true;error.value='';try{const result=await applyDelayStart({client_id:form.client_id,requested_start:`${form.requested_start}+08:00`,reason:form.reason});ElMessage.success(result.message);visible.value=false;emit('saved')}catch(e){error.value=typeof e.detail==='string'?e.detail:'申请未确认提交成功，请重试'}finally{saving.value=false}}
</script>

<style>.delay-start-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.delay-start-dialog>.el-dialog__header,.delay-start-dialog>.el-dialog__footer{flex-shrink:0}.delay-start-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.delay-start-dialog>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
