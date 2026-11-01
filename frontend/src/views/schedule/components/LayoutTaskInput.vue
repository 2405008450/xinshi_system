<template>
  <div class="layout-task-input">
    <el-checkbox-group :model-value="choices" :aria-label="`${label}固定任务`" @update:model-value="setChoices"><el-checkbox v-for="option in options" :key="option" :value="option">{{option}}</el-checkbox></el-checkbox-group>
    <el-input :model-value="extra" type="textarea" :autosize="{minRows:2,maxRows:6}" maxlength="10000" :aria-label="`${label}补充内容`" placeholder="可填写其他具体任务或补充说明，支持自由输入" @update:model-value="setExtra" />
    <div class="layout-task-add"><el-input v-model="newOption" maxlength="80" placeholder="输入自定义固定任务" :aria-label="`${label}新增固定选项`" @keyup.enter.prevent="addOption" /><el-button :loading="saving" :disabled="!newOption.trim()" @click="addOption">添加固定选项</el-button></div>
  </div>
</template>
<script setup>
import {computed,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {createLayoutTaskPreset} from '@/api/tasks'
import {defaultLayoutTasks,layoutTaskExtra,layoutTaskContent} from '@/utils/layoutReportTasks'
const props=defineProps({modelValue:{type:String,default:''},choices:{type:Array,default:()=>[]},presets:{type:Array,default:()=>defaultLayoutTasks},label:{type:String,default:'具体任务'}})
const emit=defineEmits(['update:modelValue','update:choices','change','presets-change'])
const extra=computed(()=>layoutTaskExtra(props.modelValue,props.choices))
const localOptions=ref([]),newOption=ref(''),saving=ref(false)
const options=computed(()=>[...new Set([...defaultLayoutTasks,...props.presets,...localOptions.value,...props.choices])])
function update(choices,text){const content=layoutTaskContent(choices,text);if(content.length>10000){ElMessage.warning('具体任务合计不能超过10000字');return}emit('update:choices',choices);emit('update:modelValue',content);emit('change')}
function setChoices(values){update(values,extra.value)}
function setExtra(value){update(props.choices,value)}
async function addOption(){const name=newOption.value.trim();if(!name||saving.value)return;if(options.value.includes(name)){ElMessage.info('该固定选项已存在');return}saving.value=true;try{const data=await createLayoutTaskPreset(name);localOptions.value=data.layout_task_presets||[];emit('presets-change',data);newOption.value='';ElMessage.success('固定选项已保存')}catch(error){ElMessage.error(error.detail||'添加固定选项失败')}finally{saving.value=false}}
</script>
<style scoped>.layout-task-input{width:100%}.layout-task-input :deep(.el-checkbox){margin-right:12px;height:26px}.layout-task-add{display:flex;gap:6px;margin-top:6px}.layout-task-add .el-input{min-width:0}.layout-task-add .el-button{padding:6px}</style>
