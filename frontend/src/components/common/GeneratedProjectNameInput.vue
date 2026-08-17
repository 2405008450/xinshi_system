<template>
  <el-input
    :model-value="modelValue"
    :placeholder="placeholder"
    @update:model-value="$emit('update:modelValue', $event)"
    @input="$emit('manual-input', $event)"
  >
    <template #append>
      <el-button :loading="loading" @click="$emit('regenerate')">重新生成</el-button>
    </template>
  </el-input>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '可手工填写，或根据项目信息自动生成' },
  loading: Boolean,
})

defineEmits(['update:modelValue', 'manual-input', 'regenerate'])
</script>
