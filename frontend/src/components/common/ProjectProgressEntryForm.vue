<template>
  <AppForm ref="formRef" :model="modelValue" :rules="rules" :disabled="disabled || saving" label-width="86px" @submit.prevent="submit">
    <el-row :gutter="16">
      <el-col :xs="24" :sm="12"><el-form-item label="项目状态" prop="projectStatus"><el-select :model-value="modelValue.projectStatus" style="width:100%" @update:model-value="value=>patch('projectStatus',value)"><el-option v-for="item in statuses" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :sm="12"><el-form-item label="节点时间" prop="effectiveOn"><el-date-picker :model-value="modelValue.effectiveOn" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" @update:model-value="value=>patch('effectiveOn',value)" /></el-form-item></el-col>
    </el-row>
    <el-form-item label="进度/说明" prop="changeNote"><el-input :model-value="modelValue.changeNote" type="textarea" :rows="3" maxlength="10000" show-word-limit placeholder="填写项目进度或状态变更说明" @update:model-value="value=>patch('changeNote',value)" /></el-form-item>
    <el-form-item><el-button v-if="showSubmit" type="primary" :loading="saving" @click="submit">保存项目进度</el-button><span class="project-progress-hint">状态不变时追加进度，选择新状态时一并更新状态。</span></el-form-item>
  </AppForm>
</template>
<script setup>
import {ref} from 'vue'
import AppForm from './AppForm.vue'
const props=defineProps({modelValue:{type:Object,required:true},statuses:{type:Array,required:true},saving:Boolean,disabled:Boolean,showSubmit:{type:Boolean,default:true}})
const emit=defineEmits(['update:modelValue','submit'])
const formRef=ref()
const rules={projectStatus:[{required:true,message:'请选择项目状态',trigger:'change'}],effectiveOn:[{required:true,message:'请选择节点时间',trigger:'change'}],changeNote:[{required:true,whitespace:true,message:'请填写进度/说明',trigger:'blur'},{max:10000,message:'进度/说明不能超过10000字',trigger:'blur'}]}
function patch(key,value){emit('update:modelValue',{...props.modelValue,[key]:value})}
async function submit(){if(await formRef.value?.validate().catch(()=>false))emit('submit')}
defineExpose({submit})
</script>
<style scoped>.project-progress-hint{font-size:12px;color:var(--el-text-color-secondary);margin-left:12px}</style>
