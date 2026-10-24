<template>
  <DraggableFormDialog class="paired-form-editor" :model-value="modelValue" @update:model-value="$emit('update:modelValue',$event)" :before-close="beforeClose" width="min(920px, calc(100vw - 32px))" top="5vh" append-to-body @closed="clearFieldSearch">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="title" :subtitle="subtitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" :inert="saving">
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="form-error"><el-button v-if="conflict" @click="$emit('reload')">重新加载（保留草稿供复制）</el-button></el-alert>
      <AppForm ref="formRef" :model="value" :rules="rules" label-position="top">
        <el-row :gutter="16">
          <el-col v-for="field in visibleFields" :key="field.key" :xs="24" :md="field.wide ? 24 : 12">
            <el-form-item :label="field.label" :prop="field.key">
              <ReadonlyField v-if="field.type==='readonly'" :model-value="value[field.key]" source="auto" />
              <el-select v-else-if="field.type==='select'" v-model="value[field.key]" :multiple="field.multiple" filterable clearable style="width:100%">
                <el-option v-for="option in field.options || []" :key="option.value" :value="option.value" :label="option.label" />
              </el-select>
              <el-checkbox v-else-if="field.type==='boolean'" v-model="value[field.key]">{{ field.hint || field.label }}</el-checkbox>
              <el-date-picker v-else-if="field.type==='datetime'" v-model="value[field.key]" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss[+08:00]" style="width:100%" />
              <el-date-picker v-else-if="field.type==='date'" v-model="value[field.key]" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              <el-input-number v-else-if="field.type==='number'" v-model="value[field.key]" :precision="2" style="width:100%" />
              <el-input v-else v-model="value[field.key]" :type="field.type==='textarea'?'textarea':'text'" :rows="field.type==='textarea'?4:undefined" :maxlength="field.maxlength || 20000" :placeholder="field.hint" />
            </el-form-item>
          </el-col>
        </el-row>
        <slot />
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="beforeClose(()=>{$emit('update:modelValue',false)})">取消</el-button><el-button type="primary" :loading="saving" @click="submit">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {ElMessageBox} from 'element-plus'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,title:String,subtitle:String,value:{type:Object,required:true},fields:{type:Array,default:()=>[]},saving:Boolean,error:String,conflict:Boolean})
const emit=defineEmits(['update:modelValue','save','reload'])
const bodyRef=ref(),formRef=ref(),initial=ref('')
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(bodyRef)
const visibleFields=computed(()=>props.fields.filter(field=>!field.when || field.when(props.value)))
const rules=computed(()=>Object.fromEntries(visibleFields.value.map(field=>{
  const items=[]
  if(typeof field.required==='function'?field.required(props.value):field.required){const type=field.multiple?'array':field.type==='number'?'number':field.type==='boolean'?'boolean':'string';items.push({required:true,type,...(type==='string'?{whitespace:true}:{}),message:`请填写${field.label}`,trigger:'change'})}
  if(field.key==='person2_id')items.push({validator:(_rule,value,done)=>done(value&&value===props.value.person1_id?new Error('请选择不同的两名采集员'):undefined),trigger:'change'})
  if(field.type==='datetime'&&field.key.endsWith('_end'))items.push({validator:(_rule,value,done)=>{const start=props.value[field.key.replace('_end','_start')];done(start&&value&&new Date(value)<new Date(start)?new Error('结束时间不能早于开始时间'):undefined)},trigger:'change'})
  return [field.key,items]
})))
watch(()=>props.modelValue,value=>{if(value){initial.value=JSON.stringify(props.value);formRef.value?.clearValidate()}},{flush:'post'})
const beforeClose=async done=>{if(props.saving)return;if(JSON.stringify(props.value)!==initial.value){try{await ElMessageBox.confirm('当前修改尚未保存，是否放弃本次修改？','未保存的修改',{confirmButtonText:'放弃修改',cancelButtonText:'保留草稿'})}catch{return}}done()}
const submit=async()=>{if(await formRef.value?.validate().catch(()=>false))emit('save')}
</script>
<style scoped>.form-error{margin-bottom:16px}</style>
