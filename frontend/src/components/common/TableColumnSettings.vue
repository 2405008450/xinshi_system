<template>
  <el-popover
    trigger="click"
    placement="bottom-end"
    :width="secondaryColumns.length ? 620 : (columnCount > 1 ? 520 : 280)"
    popper-class="table-column-settings-popover"
  >
    <template #reference>
      <el-button>字段设置</el-button>
    </template>
    <div class="column-settings">
      <div class="column-settings__section-header">
        <div>
          <div class="column-settings__section-title">{{ title }}</div>
          <div class="column-settings__summary">
            <span>可选字段 {{ columns.length }} 项</span>
            <span>已选择 {{ modelValue.length }} 项</span>
          </div>
        </div>
        <el-button link type="primary" @click="$emit('reset')">恢复默认</el-button>
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

      <template v-if="secondaryColumns.length">
        <el-divider />
        <div class="column-settings__section-header">
          <div>
            <div class="column-settings__section-title">{{ secondaryTitle }}</div>
            <div class="column-settings__summary">
              <span>可选字段 {{ secondaryColumns.length }} 项</span>
              <span>已选择 {{ secondaryModelValue.length }} 项</span>
            </div>
          </div>
          <el-button link type="primary" @click="$emit('resetSecondary')">恢复默认</el-button>
        </div>
        <div v-if="secondaryHint" class="column-settings__hint">{{ secondaryHint }}</div>
        <el-checkbox-group
          :model-value="secondaryModelValue"
          :style="{ gridTemplateColumns: `repeat(${secondaryColumnCount}, minmax(0, 1fr))` }"
          @update:model-value="$emit('update:secondaryModelValue', $event)"
        >
          <el-checkbox v-for="column in secondaryColumns" :key="column.key" :value="column.key">
            {{ column.label }}
          </el-checkbox>
        </el-checkbox-group>
      </template>
      <div class="column-settings__footer">
        <span>勾选结果即时生效并自动保存</span>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
defineProps({
  modelValue: { type: Array, required: true },
  columns: { type: Array, required: true },
  columnCount: { type: Number, default: 1 },
  hint: { type: String, default: '' },
  title: { type: String, default: '主表字段' },
  secondaryModelValue: { type: Array, default: () => [] },
  secondaryColumns: { type: Array, default: () => [] },
  secondaryColumnCount: { type: Number, default: 2 },
  secondaryTitle: { type: String, default: '子表字段' },
  secondaryHint: { type: String, default: '' }
})
defineEmits(['update:modelValue', 'update:secondaryModelValue', 'reset', 'resetSecondary'])
</script>

<style scoped>
.column-settings { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.column-settings__section-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 10px; }
.column-settings__section-title { color: var(--el-text-color-primary); font-weight: 600; }
.column-settings__summary { display: flex; gap: 16px; margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; }
.column-settings__hint { margin: 0 0 10px; padding: 8px 10px; border-radius: 4px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); font-size: 12px; line-height: 1.5; }
.column-settings :deep(.el-checkbox-group) { display: grid; column-gap: 24px; row-gap: 2px; align-items: start; }
.column-settings :deep(.el-checkbox) { width: 100%; margin-right: 0; }
.column-settings__footer { position: sticky; bottom: 0; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); color: var(--el-text-color-secondary); background: var(--el-bg-color-overlay); font-size: 12px; text-align: right; }
:global(.table-column-settings-popover) { max-width: calc(100vw - 32px) !important; }
</style>
