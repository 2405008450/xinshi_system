<template>
  <div class="generated-project-name">
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
    <div class="generated-project-name__hint">{{ hint }}</div>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '可手工填写，或根据项目信息自动生成' },
  hint: { type: String, required: true },
  loading: Boolean,
})

defineEmits(['update:modelValue', 'manual-input', 'regenerate'])
</script>

<style scoped>
.generated-project-name {
  width: 100%;
  min-width: 0;
}

.generated-project-name__hint {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}
</style>
