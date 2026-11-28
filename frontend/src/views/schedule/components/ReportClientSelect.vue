<template>
  <div class="report-client-select">
    <el-select :model-value="modelValue?.id||''" filterable remote clearable :remote-method="search" :loading="loading" :aria-label="label" placeholder="搜索客户全称或简称" @visible-change="value=>value&&search('',true)" @update:model-value="select">
      <el-option v-for="client in choices" :key="client.id" :value="client.id" :label="client.name" />
    </el-select>
    <small v-if="error" role="alert">{{error}} <el-button link @click="search(keyword,true)">重试</el-button></small>
  </div>
</template>
<script setup>
import {computed,onBeforeUnmount,ref} from 'vue'
import {getReportClientOptions} from '@/api/tasks'
const props=defineProps({modelValue:Object,label:String})
const emit=defineEmits(['change'])
const options=ref([]),loading=ref(false),error=ref(''),keyword=ref('')
const choices=computed(()=>[...new Map([...options.value,...(props.modelValue?.id?[props.modelValue]:[])].map(row=>[row.id,row])).values()])
let timer,controller,sequence=0
function search(value,immediate=false){
 keyword.value=value;clearTimeout(timer);controller?.abort();const current=++sequence
 loading.value=false;error.value=''
 const run=async()=>{
  controller=new AbortController();loading.value=true
  try{const result=await getReportClientOptions({keyword:value,limit:50,full_name:true},{signal:controller.signal});if(current===sequence)options.value=result}
  catch(err){if(current===sequence&&!controller.signal.aborted)error.value='客户加载失败，请重试'}
  finally{if(current===sequence)loading.value=false}
 }
 if(!value.trim()||immediate)run();else timer=setTimeout(run,400)
}
function select(id){emit('change',choices.value.find(row=>row.id===id)||null)}
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
</script>
<style scoped>.report-client-select,.report-client-select .el-select{width:100%}.report-client-select small{display:block;color:#b91c1c}</style>
