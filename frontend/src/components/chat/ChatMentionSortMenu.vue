<template>
  <el-popover v-model:visible="visible" :virtual-ref="anchor" virtual-triggering :trigger="[]" placement="bottom-start" :width="210" :z-index="100050">
    <div role="menu" aria-label="@我记录排序" class="mention-sort-menu">
      <el-button v-for="option in mentionSortOptions" :key="option.value" text role="menuitemradio" :aria-checked="modelValue === option.value" :type="modelValue === option.value ? 'primary' : ''" @click="select(option.value)">{{ option.label }}{{ modelValue === option.value ? ' ✓' : '' }}</el-button>
    </div>
  </el-popover>
</template>
<script setup>
import { ref } from 'vue'
import { mentionSortOptions } from '@/utils/chatMentionSort'
defineProps({ modelValue: { type: String, default: 'time_desc' } })
const emit = defineEmits(['update:modelValue'])
const visible = ref(false), anchor = ref(null)
function open(event) {
  event.preventDefault(); event.stopPropagation()
  const rect = event.currentTarget.getBoundingClientRect()
  const x = event.clientX || rect.left, y = event.clientY || rect.bottom
  anchor.value = { getBoundingClientRect: () => ({ x, y, top: y, bottom: y, left: x, right: x, width: 0, height: 0 }) }
  visible.value = true
}
function select(value) { emit('update:modelValue', value); visible.value = false }
defineExpose({ open })
</script>
<style scoped>
.mention-sort-menu{display:flex;flex-direction:column;align-items:stretch}.mention-sort-menu .el-button{margin:0;justify-content:flex-start}
</style>
