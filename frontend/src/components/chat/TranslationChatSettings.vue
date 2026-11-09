<template>
  <DraggableFormDialog :model-value="modelValue" title="笔译项目 · 会话发送设置" width="min(760px,calc(100vw - 32px))" top="6vh" append-to-body @update:model-value="$emit('update:modelValue',$event)" @open="load">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="笔译项目 · 会话发送设置" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p>默认加入公司全体在用账号，归入当天日期文件夹。会话名称为“订单号 · 客户名称 · 项目名称”。仅选择会话渠道时发送会话。</p>
    <div ref="editorBodyRef"><AppForm v-loading="loading" :model="form" :disabled="!data.can_manage" label-width="170px">
      <el-form-item label="自动加入会话"><el-select v-model="form.participant_audience" multiple filterable clearable><el-option v-for="item in data.audience" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item>
      <el-form-item label="周一至周六默认 @"><el-select v-model="form.weekday_user_id" filterable clearable><el-option v-for="person in data.users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
      <el-form-item label="请假时替补 @"><el-select v-model="form.leave_backup_user_id" filterable clearable><el-option v-for="person in data.users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
      <el-form-item label="周日值班候选 @"><el-select v-model="form.sunday_user_ids" multiple filterable clearable><el-option v-for="person in data.users" :key="person.id" :value="person.id" :label="person.name" /></el-select><small>自动匹配当天已发布值班安排，未安排或请假者不自动 @。</small></el-form-item>
      <el-form-item label="默认补充 @"><el-select v-model="form.extra_audience" multiple filterable clearable><el-option v-for="item in data.audience" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item>
    </AppForm></div>
    <template #footer><el-button @click="$emit('update:modelValue',false)">关闭</el-button><el-button v-if="data.can_manage" type="primary" :loading="saving" @click="save">保存设置</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {reactive,ref} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
defineProps({modelValue:Boolean})
const emit=defineEmits(['update:modelValue'])
const loading=ref(false),saving=ref(false),error=ref('')
const editorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
const data=reactive({users:[],audience:[],can_manage:false,revision:0})
const form=reactive({weekday_user_id:null,leave_backup_user_id:null,sunday_user_ids:[],extra_audience:[],participant_audience:['all']})
async function load(){loading.value=true;error.value='';try{const result=await api.get('/translation-delivery/settings');Object.assign(data,result);Object.assign(form,result.settings)}catch(e){error.value=e.detail||e.message}finally{loading.value=false}}
async function save(){saving.value=true;error.value='';try{await api.put('/translation-delivery/settings',{...form,revision:data.revision});ElMessage.success('笔译项目会话设置已保存');emit('update:modelValue',false)}catch(e){error.value=e.detail||e.message}finally{saving.value=false}}
</script>
