<template>
  <DraggableFormDialog v-model="visible" title="更新任务进度" width="min(640px, calc(100vw - 32px))" top="6vh" class="issue-dialog" append-to-body :z-index="100003" :close-on-click-modal="!saving">
    <p>{{ row?.content }}</p><AppForm ref="formRef" :model="form" label-position="top"><el-form-item label="实际进度" prop="actual_progress"><el-input v-model="form.actual_progress" type="textarea" :autosize="{minRows:5,maxRows:12}" maxlength="10000" show-word-limit /></el-form-item></AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存进度</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { issueApi } from '@/api/resourceIssues'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
const emit=defineEmits(['saved'])
const visible=ref(false),row=ref(null),saving=ref(false),error=ref(''),formRef=ref(),form=reactive({actual_progress:''})
async function open(item){try{row.value=await issueApi.detail(item.id);form.actual_progress=row.value.actual_progress||'';error.value='';visible.value=true}catch(e){ElMessage.error(e.message)}}
async function save(){if(saving.value)return;saving.value=true;error.value='';try{const data=await issueApi.updateProgress(row.value.id,{revision:row.value.revision,actual_progress:form.actual_progress});emit('saved',data);visible.value=false;ElMessage.success('进度已保存')}catch(e){error.value=e.message}finally{saving.value=false}}
defineExpose({open})
</script>
