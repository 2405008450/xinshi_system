<template>
  <div class="vocabulary-clients">
    <el-select :model-value="modelValue.map(client=>client.id)" multiple filterable remote :remote-method="search" :loading="loading" :disabled="disabled" :aria-label="label" placeholder="搜索客户简称，可选择多个客户" @visible-change="opened" @update:model-value="select">
      <el-option v-for="client in choices" :key="client.id" :value="client.id" :label="client.name" />
    </el-select>
    <small v-if="!modelValue.length&&fallbackText">原填写内容：{{fallbackText}}（选择客户后替换）</small>
    <small v-if="error" role="alert">{{error}} <el-button link type="primary" @click="search(query,true)">重试</el-button></small>
    <small v-else-if="!disabled">客户简称支持多关键词搜索，可多选{{options.length===50?'；最多显示50项，请输入简称缩小范围':''}}</small>
  </div>
</template>

<script setup>
import {computed,onBeforeUnmount,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {getReportClientOptions} from '@/api/tasks'
const props=defineProps({modelValue:{type:Array,default:()=>[]},disabled:Boolean,label:String,fallbackText:String})
const emit=defineEmits(['change'])
const options=ref([]),loading=ref(false),error=ref(''),query=ref('')
const choices=computed(()=>[...new Map([...options.value,...props.modelValue].map(client=>[client.id,client])).values()])
let timer,controller,sequence=0,loaded=false
function search(value,immediate=false){
  query.value=value;clearTimeout(timer);controller?.abort();const request=++sequence
  loading.value=false;error.value=''
  const run=async()=>{
    controller=new AbortController();loading.value=true
    try{const result=await getReportClientOptions({keyword:value,limit:50},{signal:controller.signal});if(request===sequence){options.value=result;loaded=true}}
    catch(err){if(request===sequence&&err.code!=='ERR_CANCELED'&&err.name!=='AbortError')error.value='客户简称加载失败，请重试'}
    finally{if(request===sequence)loading.value=false}
  }
  if(!value||immediate)run();else timer=setTimeout(run,400)
}
function opened(visible){if(visible&&!loaded)search('',true)}
function select(ids){
  const clients=ids.map(id=>choices.value.find(client=>client.id===id)).filter(Boolean)
  if(clients.map(client=>client.name).join('、').length>255){ElMessage.warning('所选客户简称合计不能超过255字，请分行填写');return}
  emit('change',clients.map(({id,name})=>({id,name})))
}
onBeforeUnmount(()=>{clearTimeout(timer);controller?.abort();sequence++})
</script>

<style scoped>
.vocabulary-clients{width:100%}.vocabulary-clients .el-select{width:100%}.vocabulary-clients small{display:block;color:#64748b;line-height:1.5;margin-top:4px}
</style>
