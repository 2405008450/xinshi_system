<template>
  <el-autocomplete :model-value="displayValue" :fetch-suggestions="suggest" value-key="name"
    :debounce="400" clearable :trigger-on-focus="true" :placeholder="placeholder"
    aria-label="筛选客户简称" style="width:100%" @update:model-value="update"
    @select="select" @keyup.enter="$emit('enter')">
    <template #default="{item}">
      <div class="client-filter-option"><span>{{item.name}}</span><small>{{item.fullName}} {{item.code}}</small></div>
    </template>
  </el-autocomplete>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { getClient, getClients } from '@/api/clients'
const props=defineProps({modelValue:{type:String,default:''},placeholder:{type:String,default:'输入客户简称、全称或编号'}})
const emit=defineEmits(['update:modelValue','text-input','change','enter'])
const displayValue=ref(props.modelValue)
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
let sequence=0,controller,lookupSequence=0,lookupController
watch(()=>props.modelValue,async value=>{
  displayValue.value=value
  const current=++lookupSequence
  lookupController?.abort()
  if(!uuid.test(value))return
  lookupController=new AbortController()
  try{
    const client=await getClient(value,{signal:lookupController.signal})
    if(current!==lookupSequence)return
    const name=client.client_short_name||client.client_name
    if(name){displayValue.value=name;emit('update:modelValue',name)}
  }catch{/* 无权访问或网络异常时保留用户输入，允许重新填写。 */}
},{immediate:true})
function update(value){lookupSequence++;lookupController?.abort();displayValue.value=value;emit('update:modelValue',value);emit('text-input',value)}
function select(item){update(item.name);emit('change',item.name)}
async function suggest(keyword,callback){
  const current=++sequence
  controller?.abort();controller=new AbortController()
  try{
    const rows=await getClients({skip:0,limit:20,keyword:keyword?.trim()||undefined},{signal:controller.signal})
    if(current!==sequence)return
    callback((Array.isArray(rows)?rows:[]).map(row=>({
      name:row.client_short_name||row.client_name||'',fullName:row.client_name||'',code:row.client_code||'',
    })).filter(row=>row.name))
  }catch{if(current===sequence)callback([])}
}
onBeforeUnmount(()=>{sequence++;lookupSequence++;controller?.abort();lookupController?.abort()})
</script>
<style scoped>
.client-filter-option{display:flex;flex-direction:column;line-height:1.6;padding:4px 0}
.client-filter-option small{color:var(--el-text-color-secondary)}
</style>
