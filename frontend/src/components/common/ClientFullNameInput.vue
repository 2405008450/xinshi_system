<template>
  <ReadonlyField v-if="clientId" v-bind="$attrs" :model-value="modelValue" source="auto" placeholder="选择客户后自动带出" />
  <el-autocomplete v-else v-bind="$attrs" :model-value="modelValue" :fetch-suggestions="search" value-key="client_name" :debounce="400" :trigger-on-focus="true" clearable :placeholder="placeholder" style="width:100%" @update:model-value="$emit('update:modelValue',$event)" @select="select">
    <template #default="{item}">
      <div class="client-full-name-option"><span>{{item.client_name}} <el-tag v-if="item.sub_client_id" size="small" type="warning">子客户</el-tag></span><small>{{item.client_short_name}} · {{item.client_code || item.sub_client_code || '未生成编号'}}{{item.parent_client_short_name ? ' · 归属 '+item.parent_client_short_name : ''}}</small></div>
    </template>
  </el-autocomplete>
</template>
<script setup>
import {onBeforeUnmount,watch} from 'vue'
import ReadonlyField from './ReadonlyField.vue'
import {getClients} from '@/api/clients'
import {flattenProjectClientOptions} from '@/utils/projectClientAutocomplete'
defineOptions({inheritAttrs:false})
const props=defineProps({modelValue:{type:String,default:''},clientId:{type:String,default:''},includeSubClients:Boolean,placeholder:{type:String,default:'输入客户全称搜索，或填写新客户全称'}})
const emit=defineEmits(['update:modelValue','select'])
let sequence=0,controller
async function search(value,callback){
  const current=++sequence
  controller?.abort();controller=new AbortController()
  try{
    const rows=await getClients({skip:0,limit:20,client_name:String(value||'').trim()||undefined,frequent_first:true},{signal:controller.signal})
    if(current!==sequence||props.clientId)return
    callback(props.includeSubClients?flattenProjectClientOptions(rows):(Array.isArray(rows)?rows:[]))
  }catch{if(current===sequence&&!props.clientId)callback([])}
}
function select(item){emit('update:modelValue',item.client_name||'');emit('select',item)}
watch(()=>props.clientId,()=>{sequence++;controller?.abort()})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
.client-full-name-option{display:flex;flex-direction:column;line-height:1.6;padding:4px 0}.client-full-name-option small{color:var(--el-text-color-secondary)}
</style>
