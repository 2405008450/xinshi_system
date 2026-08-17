<template>
  <div class="dialog-field-search-header">
    <div class="dialog-field-search-header__heading">
      <span class="dialog-field-search-header__title">{{ title }}</span>
      <span v-if="subtitle" class="dialog-field-search-header__subtitle">{{ subtitle }}</span>
    </div>
    <div class="dialog-field-search-header__search">
      <el-autocomplete
        ref="autocompleteRef"
        :model-value="modelValue"
        class="project-field-search"
        :fetch-suggestions="fetchSuggestions"
        value-key="label"
        :trigger-on-focus="false"
        clearable
        :placeholder="placeholder"
        popper-class="project-field-search-popper"
        aria-label="搜索项目表单字段"
        @update:model-value="$emit('update:modelValue', $event)"
        @select="$emit('select', $event)"
        @clear="$emit('clear')"
        @keyup.esc.stop="$emit('clear')"
      >
        <template #default="{ item }">
          <div class="project-field-search-option">
            <span>{{ item.label }}</span>
            <span class="project-field-search-option__location">{{ item.location }}</span>
          </div>
        </template>
      </el-autocomplete>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  modelValue: { type: String, default: '' },
  fetchSuggestions: { type: Function, required: true },
  placeholder: { type: String, default: '搜索字段，如客户交稿时间' },
})

defineEmits(['update:modelValue', 'select', 'clear'])

const autocompleteRef = ref(null)
defineExpose({ blur: () => autocompleteRef.value?.blur?.() })
</script>

<style scoped>
.dialog-field-search-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  gap: 16px;
  padding-right: 36px;
}
.dialog-field-search-header__heading {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  min-width: max-content;
  gap: 3px;
}
.dialog-field-search-header__title {
  color: var(--el-text-color-primary);
  font-size: var(--el-dialog-title-font-size);
  font-weight: 600;
  line-height: var(--el-dialog-font-line-height);
  white-space: nowrap;
}
.dialog-field-search-header__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.35;
}
.dialog-field-search-header__search {
  flex: 0 1 340px;
  width: 340px;
  min-width: 220px;
  max-width: 100%;
}
.dialog-field-search-header__search :deep(.project-field-search) { width: 100%; }
.project-field-search-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  gap: 20px;
}
.project-field-search-option > span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.project-field-search-option__location {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

@media (max-width: 768px) {
  .dialog-field-search-header {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }
  .dialog-field-search-header__heading { min-width: 0; }
  .dialog-field-search-header__title { white-space: normal; }
  .dialog-field-search-header__search { flex-basis: auto; width: 100%; min-width: 0; }
}
</style>

<style>
.project-field-search-popper { max-width: calc(100vw - 32px); }
.project-field-search-popper .el-autocomplete-suggestion li { height: auto; min-height: 34px; line-height: 1.4; }
.is-dialog-field-search-highlight {
  outline: 2px solid var(--el-color-warning);
  outline-offset: 3px;
  border-radius: 6px;
  background: var(--el-color-warning-light-8);
  box-shadow: 0 0 0 6px rgb(230 162 60 / 18%);
  animation: dialog-field-search-pulse 0.75s ease-in-out 2;
  transition: background-color 0.2s ease, outline-color 0.2s ease, box-shadow 0.2s ease;
}
@keyframes dialog-field-search-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgb(230 162 60 / 16%); }
  50% { box-shadow: 0 0 0 9px rgb(230 162 60 / 30%); }
}
@media (prefers-reduced-motion: reduce) {
  .is-dialog-field-search-highlight { animation: none; }
}
</style>
