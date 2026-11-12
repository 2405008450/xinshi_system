<template>
  <el-select :model-value="modelValue" :disabled="disabled" placeholder="选择统计口径（数量可后补）" aria-label="统计口径" @update:model-value="emit('update:modelValue',$event)">
    <el-option v-for="option in options" :key="option.value" :value="option.value" :label="option.label" :disabled="option.disabled" />
  </el-select>
  <small v-if="matrix" :class="{'quantity-basis-warning':resolved.error}">{{resolved.error||quantitySummary}}</small>
</template>
<script setup>
import {computed} from 'vue'
import {WORD_COUNT_METRICS} from '@/utils/wordCountMatrix'
import {rateQuantityOptions,resolveRateQuantity,resolvedBasisLabel,metricName} from '@/utils/translationQuantityBasis'
const props=defineProps({modelValue:String,matrix:Object,disabled:Boolean,referenceMode:Boolean})
const emit=defineEmits(['update:modelValue'])
const resolved=computed(()=>resolveRateQuantity(props.matrix,props.modelValue))
const automatic=computed(()=>!props.referenceMode&&props.modelValue==='customer_auto'&&!!resolved.value.metric)
const quantitySummary=computed(()=>{
  const {quantity,metric}=resolved.value
  if(automatic.value)return `系统自动选择 · 数量 ${quantity} ${metricName(metric)}`
  const source=String(props.modelValue).startsWith('company_')?'我司统计':'客户统计'
  return `${source}：${quantity} ${metricName(metric)}`
})
const options=computed(()=>{
  if(!props.referenceMode){
    const items=rateQuantityOptions(props.matrix,props.modelValue)
    if(automatic.value)items[0].label=resolvedBasisLabel(props.modelValue,resolved.value)
    return items
  }
  const items=WORD_COUNT_METRICS.map(item=>({value:`customer_auto:${item.key}`,label:item.label}))
  if(props.modelValue&&!items.some(item=>item.value===props.modelValue))items.push({value:props.modelValue,label:props.modelValue==='customer_auto'?'历史自动口径（请明确单位）':metricName(String(props.modelValue).replace(/^company_/,'')),disabled:props.modelValue==='customer_auto'})
  return items
})
</script>
<style scoped>small{display:block;margin-top:4px;font-size:12px;color:var(--el-text-color-secondary)}.quantity-basis-warning{color:var(--el-color-warning)}</style>
