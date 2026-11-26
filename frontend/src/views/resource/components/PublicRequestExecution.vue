<template>
  <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" data-auto-draft="off">
    <el-alert title="指定执行人填写并提交后，系统自动通知全体；重复提交不会重复发送全体通知。" type="info" :closable="false" />
    <el-form-item label="公众号执行说明" prop="content"><el-input v-model="form.content" type="textarea" :rows="4" maxlength="5000" show-word-limit :disabled="disabled || sending" placeholder="填写公众号发布内容、链接或执行结果" /></el-form-item>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-button type="primary" :loading="sending" :disabled="disabled" @click="reply">提交公众号执行说明</el-button>
  </AppForm>
</template>
<script setup>
import {reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import {sendPublicDispatchExecution} from '@/api/resourceRequests'
const props=defineProps({batchId:String,disabled:Boolean})
const emit=defineEmits(['replied'])
const form=reactive({content:''}),formRef=ref(),sending=ref(false),error=ref('')
const rules={content:[{validator:(_rule,value,done)=>value.trim()?done():done(new Error('请填写公众号执行说明')),trigger:'blur'}]}
let retryKey='',signature=''
async function reply(){
  if(sending.value||props.disabled||!await formRef.value?.validate().catch(()=>false))return
  sending.value=true;error.value=''
  try{
    const next=JSON.stringify([props.batchId,form.content.trim()])
    if(next!==signature){signature=next;retryKey=crypto.randomUUID()}
    const result=await sendPublicDispatchExecution(props.batchId,{content:form.content,idempotency_key:retryKey})
    emit('replied',result);form.content='';signature='';retryKey=''
    ElMessage.success('公众号执行说明已保存，全体通知已发送')
  }catch(e){error.value=e.detail||e.message||'提交失败，请重试'}finally{sending.value=false}
}
watch(()=>props.batchId,()=>{form.content='';error.value='';signature='';retryKey=''})
defineExpose({reply})
</script>
