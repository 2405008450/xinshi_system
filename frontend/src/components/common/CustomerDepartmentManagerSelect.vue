<template>
  <div><el-select :model-value="modelValue" multiple filterable clearable collapse-tags collapse-tags-tooltip :loading="loading" placeholder="选择客户部成员（可多选）" aria-label="指定客户经理（可多选）" style="width:100%" @update:model-value="emit('update:modelValue',$event)"><el-option v-for="person in people" :key="person.id" :value="person.id" :label="label(person)" /></el-select><el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error" link @click="load">重新加载客户部成员</el-button></div>
</template>
<script setup>
import {ref,onMounted,onBeforeUnmount} from 'vue'
import {getFinanceManagerOptions} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
defineProps({modelValue:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:modelValue','options'])
const people=ref([]),loading=ref(false),error=ref('')
let sequence=0,controller
const label=person=>`${person.name}${person.username&&person.username!==person.name?`（${person.username}）`:''}${person.active?'':'（已停用）'}`
async function load(){const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getFinanceManagerOptions({signal:controller.signal});if(current===sequence){people.value=data.items||[];emit('options',people.value)}}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户部成员加载失败')}finally{if(current===sequence)loading.value=false}}
onMounted(load)
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
