<template>
  <div class="membership-tags"><el-tag v-if="groups.length>1" type="warning" size="small">跨部门 {{ groups.length }}</el-tag><el-tag v-for="dept in groups" :key="dept.name" size="small" :type="dept.name===primary ? 'primary':'info'">{{ dept.name }}{{ dept.position ? ` · ${dept.position}` : '' }}</el-tag><span v-if="!groups.length">未分部门</span></div>
</template>
<script setup>
import { computed } from 'vue'
const props=defineProps({userId:{type:String,required:true},primary:{type:String,default:''},people:{type:Array,default:()=>[]}})
const groups=computed(()=>props.people.find(p=>p.id===props.userId)?.departments||(props.primary?[{name:props.primary}]:[]))
</script>
<style scoped>.membership-tags{display:flex;flex-wrap:wrap;gap:5px}</style>
