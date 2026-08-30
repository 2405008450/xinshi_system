<template>
  <ColumnHeaderFilter
    :label="definition.label"
    :active="active"
    :width="definition.headerWidth || (definition.wide ? 320 : 240)"
    :placement="placement"
    @clear="clear"
  >
    <template #label><slot name="label">{{ definition.label }}</slot></template>
    <ListFilterControl
      :model-value="modelValue"
      :definition="definition"
      @update:model-value="$emit('update:modelValue', $event)"
      @text-input="$emit('text-input', $event)"
      @change="$emit('change', $event)"
      @enter="$emit('enter')"
    />
  </ColumnHeaderFilter>
</template>

<script setup>
import { computed } from 'vue'
import ColumnHeaderFilter from './ColumnHeaderFilter.vue'
import ListFilterControl from './ListFilterControl.vue'
import { emptyFilterValue, isActiveFilterValue } from '@/utils/listFieldFilters'

const props = defineProps({
  definition: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: '' },
  placement: { type: String, default: 'bottom-start' },
})

const emit = defineEmits(['update:modelValue', 'text-input', 'change', 'enter', 'clear'])
const active = computed(() => isActiveFilterValue(props.definition, props.modelValue))
const clear = () => {
  emit('update:modelValue', emptyFilterValue(props.definition))
  emit('clear')
}
</script>
