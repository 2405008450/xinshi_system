<template>
  <el-select :model-value="modelValue" :disabled="disabled" placeholder="选择统计口径（数量可后补）" aria-label="统计口径" @update:model-value="emit('update:modelValue',$event)">
    <el-option v-for="option in options" :key="option.value" :value="option.value" :label="option.label" />
  </el-select>
</template>
<script setup>
import {computed} from 'vue'
import {rateQuantityOptions} from '@/utils/translationQuantityBasis'
const props=defineProps({modelValue:String,matrix:Object,disabled:Boolean})
const emit=defineEmits(['update:modelValue'])
const options=computed(()=>rateQuantityOptions(props.matrix,props.modelValue))
</script>
