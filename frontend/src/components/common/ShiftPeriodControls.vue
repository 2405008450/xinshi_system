<template>
  <div class="shift-period-controls">
    <div class="shift-period-main"><el-radio-group v-if="weekly" :model-value="mode" :disabled="disabled" :aria-label="action==='统计'?'考勤统计周期':'排班周期'" @update:model-value="value=>$emit('update:mode',value)"><el-radio-button value="week">{{weekLabel||`每周${action}`}}</el-radio-button><el-radio-button value="month">每月{{action}}</el-radio-button></el-radio-group>
      <el-date-picker v-if="showPicker" :model-value="value" :type="mode==='week'?'date':'month'" :value-format="mode==='week'?'YYYY-MM-DD':'YYYY-MM'" :format="mode==='week'?'YYYY-MM-DD [所在周]':'YYYY-MM'" :clearable="false" :disabled="disabled" :aria-label="mode==='week'?'排班周（选择周内任意一天）':'排班月份'" @update:model-value="select" />
      <el-button link :aria-expanded="expanded" :disabled="disabled" @click="expanded=!expanded">{{action==='安排'?'快速查看':`快捷${action}`}}{{expanded?'（收起）':'（展开）'}}</el-button>
    </div>
    <el-collapse-transition><div v-show="expanded" class="shift-period-shortcuts"><template v-if="weekly"><el-button :disabled="disabled" @click="chooseWeek(-1)">上周{{action}}</el-button><el-button :disabled="disabled" @click="chooseWeek(0)">本周{{action}}</el-button><el-button :disabled="disabled" @click="chooseWeek(1)">下周{{action}}</el-button></template><el-button :disabled="disabled" @click="chooseMonth(-1)">上月{{action}}</el-button><el-button :disabled="disabled" @click="chooseMonth(0)">本月{{action}}</el-button><el-button :disabled="disabled" @click="chooseMonth(1)">下月{{action}}</el-button></div></el-collapse-transition>
  </div>
</template>
<script setup>
import {ref} from 'vue'
import {currentShiftWeek,shiftWeek,currentShiftMonth,shiftMonth} from '@/utils/monthlyShift'
const props=defineProps({mode:{type:String,default:'week'},value:{type:String,required:true},disabled:Boolean,action:{type:String,default:'安排'},weekly:{type:Boolean,default:true},weekLabel:{type:String,default:''},showPicker:{type:Boolean,default:true}}),emit=defineEmits(['update:mode','update:value'])
const expanded=ref(false)
function select(value){if(!value||props.disabled)return;emit('update:value',props.mode==='week'?shiftWeek(value):value)}
function chooseWeek(offset){if(props.disabled)return;emit('update:mode','week');emit('update:value',shiftWeek(currentShiftWeek(),offset))}
function chooseMonth(offset){if(props.disabled)return;emit('update:mode','month');emit('update:value',shiftMonth(currentShiftMonth(),offset))}
</script>
<style scoped>.shift-period-controls{display:flex;flex-direction:column;gap:8px;min-width:0}.shift-period-main,.shift-period-shortcuts{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.shift-period-controls :deep(.el-button+.el-button){margin-left:0}.shift-period-controls :deep(.el-date-editor){width:205px;max-width:100%}.shift-period-shortcuts{padding:8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc}</style>
