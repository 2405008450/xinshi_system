<template>
  <div v-if="readonly" class="resume-year-display"><span>{{label}}</span><span>{{modelValue||'-'}}</span></div>
  <el-form-item v-else class="resume-year-field" :label="label" :prop="fieldPath"><YearInput :model-value="modelValue" maxlength="50" placeholder="2026" :aria-label="label" @update:model-value="$emit('update:modelValue',$event)" /></el-form-item>
</template>
<script setup>
import {computed} from 'vue'
import {ElInput as YearInput} from 'element-plus'
import 'element-plus/es/components/input/style/css'
const props=defineProps({modelValue:String,fieldPath:String,readonly:Boolean,bilingual:Boolean})
defineEmits(['update:modelValue'])
const label=computed(()=>props.bilingual?'简历年份 / Resume year':'简历年份')
</script>
<style scoped>
.resume-year-field.el-form-item{display:flex;flex-direction:row;align-items:center;gap:8px;margin-bottom:0;max-width:100%}.resume-year-field :deep(.el-form-item__label){padding:0;line-height:32px;height:auto;white-space:nowrap}.resume-year-field :deep(.el-form-item__content){flex:1;min-width:0}.resume-year-field :deep(.el-input){width:140px;max-width:100%}.resume-year-display{display:flex;align-items:center;gap:8px;font-size:14px;overflow-wrap:anywhere}.resume-year-display>span:last-child{max-width:240px}
</style>
