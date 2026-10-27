<template>
  <DraggableFormDialog v-model="visible" title="增加自定义字段" width="min(460px, calc(100vw - 32px))" append-to-body destroy-on-close :close-on-click-modal="false">
    <AppForm ref="formRef" :model="form" label-position="top" @submit.prevent="save"><el-form-item label="字段名称" prop="name" :rules="[{required:true,whitespace:true,message:'请填写字段名称',trigger:'blur'}]"><el-input v-model="form.name" maxlength="100" placeholder="例如：擅长领域、联系渠道" :disabled="saving" /></el-form-item><p>新增后作为可编辑文本列，后续录入可继续使用。</p></AppForm>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">增加</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {nextTick,reactive,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {developmentApi as api} from '@/api/resourceDevelopment'
const emit=defineEmits(['created']),visible=ref(false),saving=ref(false),formRef=ref(),form=reactive({name:''})
async function open(){if(saving.value)return;form.name='';visible.value=true;await nextTick();formRef.value?.clearValidate()}
async function save(){if(saving.value)return;saving.value=true;try{if(!await formRef.value.validate().catch(()=>false))return;const field=await api.addCustomField({name:form.name.trim()});emit('created',field);visible.value=false;ElMessage.success('自定义字段已增加')}catch(error){await formRef.value?.applyServerErrors(error);ElMessage.error(error.message)}finally{saving.value=false}}
defineExpose({open})
</script>
