<template>
  <el-select :model-value="modelValue" filterable allow-create default-first-option :loading="loading" style="width:100%" placeholder="选择片区，或输入新片区后回车" @change="select">
    <el-option v-for="area in areas" :key="area.id" :value="area.id" :label="area.label" />
  </el-select>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAnnotationAreas, createAnnotationArea } from '@/api/annotationProjects'
defineProps({modelValue:String})
const emit=defineEmits(['update:modelValue','changed'])
const areas=ref([]),loading=ref(false)
onMounted(async()=>{loading.value=true;try{areas.value=await getAnnotationAreas()}catch(error){ElMessage.error(error.detail||'片区加载失败')}finally{loading.value=false}})
const select=async value=>{
  if(areas.value.some(area=>area.id===value)){emit('update:modelValue',value);return}
  loading.value=true
  try{const created=await createAnnotationArea(value);if(!areas.value.some(area=>area.id===created.id))areas.value.push(created);emit('update:modelValue',created.id);emit('changed')}
  catch(error){ElMessage.error(error.detail||'新增片区失败')}
  finally{loading.value=false}
}
</script>
