<template>
  <el-select :model-value="selected" multiple filterable clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="3" :popper-class="`chat-topic-select-popper ${popperClass}`" placeholder="选择部门或人员（可多选）" @update:model-value="change">
    <el-option-group label="批量选择"><el-option v-if="allowEveryone" label="全体" value="everyone" /><el-option label="全部部门" value="all:departments" /><el-option label="全部人员" value="all:users" /></el-option-group>
    <el-option v-if="allowEveryone && modelValue.everyone === null" label="沿用原权限" value="legacy" />
    <el-option-group label="部门"><el-option v-for="department in departments" :key="department.id" :value="`department:${department.id}`" :label="department.name" /></el-option-group>
    <el-option-group label="人员"><el-option v-for="person in users" :key="person.id" :value="`user:${person.id}`" :label="person.name" /></el-option-group>
  </el-select>
</template>
<script setup>
import { computed } from 'vue'
const props=defineProps({modelValue:{type:Object,default:()=>({})},users:{type:Array,default:()=>[]},departments:{type:Array,default:()=>[]},popperClass:{type:String,default:''},allowEveryone:Boolean})
const emit=defineEmits(['update:modelValue'])
const selected=computed(()=>props.allowEveryone && props.modelValue.everyone !== false ? [props.modelValue.everyone === null ? 'legacy' : 'everyone'] : [...(props.modelValue.departmentIds||[]).map(id=>`department:${id}`),...(props.modelValue.userIds||[]).map(id=>`user:${id}`)])
function change(values){
  if(props.allowEveryone && values.includes('everyone') && !selected.value.includes('everyone')){emit('update:modelValue',{everyone:true,departmentIds:[],userIds:[]});return}
  if(props.allowEveryone && values.every(value=>value==='everyone'||value==='legacy')){emit('update:modelValue',{everyone:values.includes('everyone') ? true : values.includes('legacy') ? null : false,departmentIds:[],userIds:[]});return}
  const expanded=new Set(values.filter(value=>!value.startsWith('all:')))
  if(values.includes('all:departments'))props.departments.forEach(row=>expanded.add(`department:${row.id}`))
  if(values.includes('all:users'))props.users.forEach(row=>expanded.add(`user:${row.id}`))
  emit('update:modelValue',{...(props.allowEveryone?{everyone:false}:{}),departmentIds:[...expanded].filter(value=>value.startsWith('department:')).map(value=>value.slice(11)),userIds:[...expanded].filter(value=>value.startsWith('user:')).map(value=>value.slice(5))})
}
</script>
