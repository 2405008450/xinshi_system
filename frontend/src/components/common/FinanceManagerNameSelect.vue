<template>
  <div class="finance-manager-name-select">
    <el-select v-model="model" filterable allow-create default-first-option clearable
      aria-label="选择客户经理" placeholder="选择客户经理（可搜索或输入）" :loading="loading"
      :filter-method="value=>keyword=value" @visible-change="opened" @change="emit('change',$event)">
      <el-option v-for="person in visiblePeople" :key="person.value" :value="person.value" :label="person.label" />
    </el-select>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
  </div>
</template>
<script setup>
import {computed,onMounted,onBeforeUnmount,ref} from 'vue'
import {getFinanceManagerOptions} from '@/api/translationCustomerFinance'
import {matchesSearchFields} from '@/utils/searchMatching'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const model=defineModel({type:String,default:''})
const emit=defineEmits(['change'])
const people=ref([]),keyword=ref(''),loading=ref(false),error=ref('')
const visiblePeople=computed(()=>people.value.filter(person=>matchesSearchFields([person.value,person.label],keyword.value)))
let sequence=0,controller
function opened(value){if(value){keyword.value='';if(!people.value.length&&!loading.value)void load()}}
async function load(){const seq=++sequence;controller?.abort();const request=controller=new AbortController();loading.value=true;error.value='';try{const data=await getFinanceManagerOptions({signal:request.signal});if(seq!==sequence)return;const seen=new Set();people.value=(data.items||[]).flatMap(person=>{const value=person.name||person.username;if(!value||seen.has(value))return [];seen.add(value);return [{value,label:`${value}${person.username&&person.username!==value?`（${person.username}）`:''}${person.active===false?'（已停用）':''}`}]})}catch(e){if(seq===sequence&&!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'客户经理加载失败，可重试或直接输入姓名')}finally{if(seq===sequence)loading.value=false}}
onMounted(load)
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>.finance-manager-name-select{width:100%;min-width:0}.finance-manager-name-select :deep(.el-select){width:100%}</style>
