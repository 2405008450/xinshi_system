<template>
  <el-collapse-item v-for="field in sections" :key="field.key" :name="`${prefix}-${field.key}`" :data-section-key="`${prefix}-${field.key}`" :title="label(field)">
    <ResumeExperienceGrid v-if="field.entries" :model-value="modelValue[field.key]||[]" @update:model-value="update(field.key,$event)" :prop-prefix="`${propPrefix}.${field.key}`" :group-title="label(field)" :bilingual="bilingual" :readonly="readonly" />
    <div v-else class="resume-supplement-text">
      <div v-if="readonly" class="pre-wrap">{{modelValue[field.key]||'—'}}</div>
      <el-form-item v-else :label="label(field)" :prop="`${propPrefix}.${field.key}`"><GridInput :model-value="modelValue[field.key]||''" @update:model-value="update(field.key,$event)" type="textarea" :autosize="{minRows:3,maxRows:10}" maxlength="20000" /></el-form-item>
    </div>
  </el-collapse-item>
</template>
<script setup>
import {computed} from 'vue'
import {ElInput as GridInput} from 'element-plus'
import ResumeExperienceGrid from './ResumeExperienceGrid.vue'
import {resumeSupplementSections} from '@/utils/talentResumeSections'
const props=defineProps({modelValue:{type:Object,required:true},group:String,prefix:{type:String,default:'resume-supplement'},propPrefix:{type:String,default:'resumeProfile'},readonly:Boolean,bilingual:Boolean})
const emit=defineEmits(['update:modelValue'])
const sections=computed(()=>resumeSupplementSections.filter(s=>s.group===props.group))
const label=field=>props.bilingual?`${field.label} / ${field.english}`:field.label
function update(key,value){emit('update:modelValue',{...props.modelValue,[key]:value})}
</script>
<style scoped>.resume-supplement-text{padding:12px}.pre-wrap{white-space:pre-wrap;overflow-wrap:anywhere}</style>
