<template>
  <div class="path-input">
    <el-input
      :model-value="modelValue"
      :placeholder="placeholder"
      clearable
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <PathActionButtons @open="$emit('open')" @copy="$emit('copy')" />
  </div>
</template>

<script setup>
import PathActionButtons from './PathActionButtons.vue'

defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入网络文件路径' },
})

defineEmits(['update:modelValue', 'open', 'copy'])
</script>

<style scoped>
.path-input {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 6px;
}

.path-input .el-input {
  flex: 1;
  min-width: 0;
}
</style>
