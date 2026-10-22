<template>
  <el-select :model-value="selected" multiple filterable clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="3" :popper-class="`chat-topic-select-popper ${popperClass}`" placeholder="选择部门或人员（可多选）" @update:model-value="change">
    <el-option-group label="批量选择"><el-option label="全部部门" value="all:departments" /><el-option label="全部人员" value="all:users" /></el-option-group>
    <el-option-group label="部门"><el-option v-for="department in departments" :key="department.id" :value="`department:${department.id}`" :label="department.name" /></el-option-group>
    <el-option-group label="人员"><el-option v-for="person in users" :key="person.id" :value="`user:${person.id}`" :label="person.name" /></el-option-group>
  </el-select>
</template>
<script setup>
import { computed } from 'vue'
const props=defineProps({modelValue:{type:Object,default:()=>({})},users:{type:Array,default:()=>[]},departments:{type:Array,default:()=>[]},popperClass:{type:String,default:''}})
const emit=defineEmits(['update:modelValue'])
const selected=computed(()=>[...(props.modelValue.departmentIds||[]).map(id=>`department:${id}`),...(props.modelValue.userIds||[]).map(id=>`user:${id}`)])
function change(values){
  const expanded=new Set(values.filter(value=>!value.startsWith('all:')))
  if(values.includes('all:departments'))props.departments.forEach(row=>expanded.add(`department:${row.id}`))
  if(values.includes('all:users'))props.users.forEach(row=>expanded.add(`user:${row.id}`))
  emit('update:modelValue',{departmentIds:[...expanded].filter(value=>value.startsWith('department:')).map(value=>value.slice(11)),userIds:[...expanded].filter(value=>value.startsWith('user:')).map(value=>value.slice(5))})
}
</script>
