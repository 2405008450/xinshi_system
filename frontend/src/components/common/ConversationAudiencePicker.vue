<template>
  <el-popover title="补充 @" placement="top-end" trigger="click" :width="360">
    <template #reference><el-button :disabled="disabled" :loading="loading" @click="load">会话补充 @{{ modelValue.length ? `（${modelValue.length}）` : '' }}</el-button></template>
    <p>补充本次发送会话的提醒对象，适用于发送会话及会话和邮件，不影响邮件收件人。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-button v-if="error" link type="primary" @click="load">重新加载</el-button>
    <el-select :model-value="modelValue" @update:model-value="$emit('update:modelValue',$event)" :loading="loading" :disabled="loading || !!error" multiple filterable clearable placeholder="可补充 @全体、部门或人员" style="width:100%">
      <el-option v-for="item in audience" :key="item.value" :value="item.value" :label="item.label" />
    </el-select>
  </el-popover>
</template>
<script setup>
import {ref} from 'vue'
import api from '@/api/index'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
defineProps({modelValue:{type:Array,default:()=>[]},disabled:Boolean})
defineEmits(['update:modelValue'])
const loading=ref(false),error=ref(''),audience=ref([])
async function load(){
 if(loading.value)return
 loading.value=true;error.value=''
 try{audience.value=(await api.get('/project-delivery/audience')).audience||[]}
 catch(reason){error.value='会话补充 @ 名单加载失败：'+getLocalizedErrorMessage(reason,'请重试')}
 finally{loading.value=false}
}
</script>
