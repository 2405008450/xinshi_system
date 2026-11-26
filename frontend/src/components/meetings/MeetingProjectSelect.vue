<template><div><el-select :model-value="projectId" :disabled="!projectType" filterable remote clearable :remote-method="search" :loading="loading" placeholder="搜索订单号、项目名称或客户" @visible-change="value=>value&&search('')" @update:model-value="selected"><el-option v-for="row in options" :key="row.id" :value="row.id" :label="`${row.order_no} · ${row.project_name}`" /><el-option v-if="projectId&&!options.some(row=>row.id===projectId)" :value="projectId" :label="label||projectId" /></el-select><small v-if="error" role="alert">{{error}}</small></div></template>
<script setup>
import {onBeforeUnmount,ref,watch} from 'vue'
import {meetingProjects} from '@/api/meetings'
const props=defineProps({projectType:String,projectId:String,label:String}),emit=defineEmits(['selected'])
const options=ref([]),loading=ref(false),error=ref('');let timer,controller,sequence=0
function search(keyword){clearTimeout(timer);controller?.abort();const id=++sequence;if(!props.projectType)return;const run=async()=>{controller=new AbortController();loading.value=true;error.value='';try{const result=await meetingProjects(props.projectType,keyword,controller.signal);if(id===sequence)options.value=result.items}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value='项目加载失败，请重新搜索'}finally{if(id===sequence)loading.value=false}};if(keyword)timer=setTimeout(run,400);else run()}
function selected(id){emit('selected',options.value.find(row=>row.id===id)||null)}
watch(()=>props.projectType,()=>{controller?.abort();sequence++;options.value=[];loading.value=false})
onBeforeUnmount(()=>{clearTimeout(timer);controller?.abort();sequence++})
</script>
