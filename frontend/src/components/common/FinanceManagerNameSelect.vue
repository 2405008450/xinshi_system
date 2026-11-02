<template><el-select v-model="model" filterable remote allow-create default-first-option :remote-method="search" :loading="loading" clearable placeholder="选择或输入客户经理" @visible-change="value=>value&&search('')"><el-option v-for="name in names" :key="name" :value="name" :label="name" /></el-select></template>
<script setup>
import {ref,onBeforeUnmount} from 'vue'
import {getUserOptions} from '@/api/users'
const model=defineModel({type:String,default:''}),names=ref([]),loading=ref(false)
let sequence=0,controller
async function search(keyword){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;try{const rows=await getUserOptions({keyword,limit:100},controller.signal);if(seq===sequence)names.value=[...new Set((rows||[]).map(row=>row.display_name||row.full_name||row.username).filter(Boolean))]}catch{/* 可以直接输入客户经理姓名。 */}finally{if(seq===sequence)loading.value=false}}
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
