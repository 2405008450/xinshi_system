<template>
  <el-select :model-value="selection" multiple @update:model-value="update">
    <el-option label="空" :value="blankOption" />
    <slot />
  </el-select>
</template>

<script setup>
import { computed } from 'vue'
import { BLANK_FILTER_VALUE, isBlankFilter } from '@/utils/listFieldFilters'

const props = defineProps({ modelValue: { type: [Array, Object], default: () => [] } })
const emit = defineEmits(['update:modelValue'])
const blankOption = '__xinshi_blank_field__'
const selection = computed(() => isBlankFilter(props.modelValue) ? [blankOption]
  : Array.isArray(props.modelValue) ? props.modelValue : [])
function update(values) {
  if (values?.includes(blankOption)) {
    emit('update:modelValue', isBlankFilter(props.modelValue) && values.length > 1
      ? values.filter(value => value !== blankOption) : BLANK_FILTER_VALUE)
  } else emit('update:modelValue', values || [])
}
</script>
