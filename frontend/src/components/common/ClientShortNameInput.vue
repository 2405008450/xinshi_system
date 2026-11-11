<template>
  <el-autocomplete v-bind="$attrs" :model-value="modelValue" :fetch-suggestions="search" value-key="client_short_name" :debounce="400" :trigger-on-focus="true" clearable :placeholder="placeholder" style="width:100%" @update:model-value="update" @input="$emit('input',$event)" @clear="$emit('clear')" @select="select">
    <template #default="{item}"><div class="client-short-name-option"><span>{{item.client_short_name}}</span><small>{{item.client_name || '尚未登记全称'}} · {{item.client_code || item.sub_client_code || '未生成编号'}}</small></div></template>
  </el-autocomplete>
</template>
<script setup>
import {onBeforeUnmount,watch} from 'vue'
import {getClients,getClient} from '@/api/clients'
import {matchesSearchFields} from '@/utils/searchMatching'

defineOptions({inheritAttrs:false})
const props=defineProps({modelValue:{type:String,default:''},fullName:{type:String,default:''},parentClientId:{type:String,default:''},placeholder:{type:String,default:'输入客户简称搜索，或填写新客户简称'}})
const emit=defineEmits(['update:modelValue','update:fullName','input','clear','select'])
let sequence=0,controller
function invalidate(){sequence++;controller?.abort()}
function update(value){invalidate();emit('update:modelValue',value)}
async function search(value,callback){
  invalidate();const current=sequence,owner=localStorage.getItem('user_id'),parent=props.parentClientId
  controller=new AbortController()
  try{
    const rows=parent
      ? (await getClient(parent,{signal:controller.signal}))?.sub_clients||[]
      : await getClients({skip:0,limit:20,client_short_name:String(value||'').trim()||undefined,frequent_first:true},{signal:controller.signal})
    if(current!==sequence||owner!==localStorage.getItem('user_id')||parent!==props.parentClientId)return
    callback((Array.isArray(rows)?rows:[]).filter(row=>!parent||matchesSearchFields([row.client_short_name,row.client_name,row.sub_client_code],value)))
  }catch{if(current===sequence&&owner===localStorage.getItem('user_id'))callback([])}
}
function select(item){
  invalidate()
  emit('update:modelValue',item.client_short_name||'')
  if(String(item.client_name||'').trim())emit('update:fullName',item.client_name)
  emit('select',item)
}
watch(()=>props.parentClientId,invalidate)
watch(()=>props.modelValue,invalidate)
window.addEventListener('auth-session-clearing',invalidate)
onBeforeUnmount(()=>{invalidate();window.removeEventListener('auth-session-clearing',invalidate)})
</script>
<style scoped>
.client-short-name-option{display:flex;flex-direction:column;line-height:1.6;padding:4px 0}.client-short-name-option small{color:var(--el-text-color-secondary)}
</style>
