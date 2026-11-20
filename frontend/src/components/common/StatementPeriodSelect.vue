<template>
  <el-select :model-value="modelValue ?? 'all'" aria-label="账期" :loading="loading"
    :disabled="loading" style="width: 160px" @change="$emit('update:modelValue',$event==='all'?undefined:$event)">
    <el-option value="all" :label="allLabel" />
    <el-option v-if="allowUnassigned" value="unassigned" label="未分账期" />
    <el-option v-for="number in periods" :key="number" :value="number" :label="`第${number}期`" />
  </el-select>
</template>

<script setup>
import {ref,watch} from 'vue'
import {getStatementPeriodOptions} from '@/api/customerStatements'
import {ElMessage} from 'element-plus'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'

const props=defineProps({modelValue:[Number,String],month:String,months:{type:Array,default:()=>[]},clientId:[String,Number],settlementScope:String,allowUnassigned:Boolean,allLabel:{type:String,default:'全部期次'}})
const emit=defineEmits(['update:modelValue'])
const periods=ref([]),loading=ref(false)
watch(()=>[props.month,props.clientId,props.settlementScope,JSON.stringify(props.months)],async ([month,clientId,scope],previous,onCleanup)=>{
  const request=new AbortController()
  onCleanup(()=>request.abort())
  periods.value=[]
  if(previous?.[0] && previous[0]!==month && props.modelValue!=='unassigned' && !props.allowUnassigned)emit('update:modelValue',undefined)
  const months=[...new Set(props.months?.length?props.months:month?[month]:[])]
  if(!months.length){loading.value=false;return}
  loading.value=true
  try{
    const results=await Promise.all(months.map(value=>getStatementPeriodOptions(value,clientId,scope,request.signal)))
    if(!request.signal.aborted)periods.value=[...new Set(results.flat())].sort((a,b)=>a-b)
  }catch(error){
    if(!request.signal.aborted)ElMessage.error(getLocalizedErrorMessage(error,'账期读取失败'))
  }finally{
    if(!request.signal.aborted)loading.value=false
  }
},{immediate:true})
</script>
