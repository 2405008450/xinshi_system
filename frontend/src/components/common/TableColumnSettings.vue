<template>
  <el-popover
    trigger="click"
    placement="bottom-end"
    :width="columnCount > 1 ? 520 : 280"
    popper-class="table-column-settings-popover"
  >
    <template #reference>
      <el-button>字段设置</el-button>
    </template>
    <div class="column-settings">
      <div class="column-settings__summary">
        <span>主表可选字段 {{ columns.length }} 项</span>
        <span>已选择 {{ modelValue.length }} 项</span>
      </div>
      <div v-if="hint" class="column-settings__hint">{{ hint }}</div>
      <el-checkbox-group
        :model-value="modelValue"
        :style="{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }"
        @update:model-value="$emit('update:modelValue', $event)"
      >
        <el-checkbox v-for="column in columns" :key="column.key" :value="column.key">
          {{ column.label }}
        </el-checkbox>
      </el-checkbox-group>
      <div class="column-settings__footer">
        <el-button link type="primary" @click="$emit('reset')">恢复默认</el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
defineProps({
  modelValue: { type: Array, required: true },
  columns: { type: Array, required: true },
  columnCount: { type: Number, default: 1 },
  hint: { type: String, default: '' }
})
defineEmits(['update:modelValue', 'reset'])
</script>

<style scoped>
.column-settings { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.column-settings__summary { position: sticky; top: 0; z-index: 1; display: flex; justify-content: space-between; gap: 16px; padding-bottom: 10px; color: var(--el-text-color-secondary); background: var(--el-bg-color-overlay); font-size: 12px; }
.column-settings__hint { margin: 0 0 10px; padding: 8px 10px; border-radius: 4px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); font-size: 12px; line-height: 1.5; }
.column-settings :deep(.el-checkbox-group) { display: grid; column-gap: 24px; row-gap: 2px; align-items: start; }
.column-settings :deep(.el-checkbox) { width: 100%; margin-right: 0; }
.column-settings__footer { position: sticky; bottom: 0; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color-overlay); text-align: right; }
:global(.table-column-settings-popover) { max-width: calc(100vw - 32px) !important; }
</style>
