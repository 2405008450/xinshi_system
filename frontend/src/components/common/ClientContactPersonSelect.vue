<template>
  <el-autocomplete :model-value="modelValue" :fetch-suggestions="suggest" value-key="name" :trigger-on-focus="true" :debounce="0" maxlength="100" clearable style="width:100%" :placeholder="loading ? '正在读取客户联系人，可直接填写' : '选择该客户的联系人，或直接填写新姓名'" @update:model-value="value=>emit('update:modelValue',value)" @select="item=>emit('update:modelValue',item.name)" />
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api'
import { matchesSearch } from '@/utils/searchMatching'
const props=defineProps({modelValue:String,clientId:String,subClientId:String})
const emit=defineEmits(['update:modelValue'])
const names=ref([]),loading=ref(false)
let sequence=0,controller,loadingPromise
async function load(){
  const request=++sequence;controller?.abort();names.value=[];loading.value=false
  if(!props.clientId)return
  controller=new AbortController();loading.value=true
  try{const result=await api.get('/client-contact-people',{params:{client_id:props.clientId,sub_client_id:props.subClientId||undefined},signal:controller.signal});if(request===sequence)names.value=result.contact_names||[]}
  catch{/* 可继续填写新联系人；接口错误由公共处理器展示。 */}
  finally{if(request===sequence)loading.value=false}
}
async function suggest(keyword,done){if(loading.value)await loadingPromise;done(names.value.filter(name=>matchesSearch(name,keyword)).map(name=>({name})))}
watch(()=>[props.clientId,props.subClientId],()=>{loadingPromise=load()},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
