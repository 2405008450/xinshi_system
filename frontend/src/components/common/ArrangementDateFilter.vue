<template>
  <div class="arrangement-date-filter">
    <el-button v-for="button in buttons" :key="button.key" :type="active===button.key?'primary':'default'" size="small" @click="choose(button.key)">{{button.label}}</el-button>
    <el-date-picker :model-value="modelValue" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" aria-label="筛选安排日期" :clearable="true" @update:model-value="update" />
  </div>
</template>
<script setup>
import {ref,watch} from 'vue'
import {arrangementDateRange} from '@/utils/taskDateRanges'
const props=defineProps({modelValue:{type:Array,default:null}})
const emit=defineEmits(['update:modelValue'])
const active=ref('today')
watch(()=>props.modelValue,value=>{if(!value)active.value='today'})
const buttons=[{key:'today',label:'今日安排'},{key:'yesterday',label:'昨日安排'},{key:'before-yesterday',label:'前日安排'},{key:'last-week',label:'上周安排'},{key:'previous-week',label:'前一周安排'}]
function choose(key){active.value=key;emit('update:modelValue',arrangementDateRange(key))}
function update(value){active.value=value?'custom':'today';emit('update:modelValue',value||null)}
</script>
<style scoped>.arrangement-date-filter{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:14px 0}.arrangement-date-filter .el-button{margin-left:0}.arrangement-date-filter :deep(.el-date-editor){max-width:100%;width:280px;flex-grow:0}</style>
