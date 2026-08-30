<template>
  <span class="column-header-filter">
    <span class="column-header-filter__label">
      <slot name="label">{{ label }}</slot>
    </span>
    <el-popover
      trigger="click"
      :placement="placement"
      :width="width"
      popper-class="column-header-filter-popover"
    >
      <template #reference>
        <button
          type="button"
          class="column-header-filter__trigger"
          :class="{ 'is-active': active }"
          :aria-label="`${label}筛选`"
          :title="`${label}筛选`"
          @click.stop
        >
          <el-icon><Filter /></el-icon>
        </button>
      </template>
      <div class="column-header-filter__content">
        <slot />
        <div class="column-header-filter__footer">
          <el-button link type="primary" size="small" :disabled="!active" @click="$emit('clear')">
            清除筛选
          </el-button>
        </div>
      </div>
    </el-popover>
  </span>
</template>

<script setup>
import { Filter } from '@element-plus/icons-vue'

defineProps({
  label: { type: String, required: true },
  active: { type: Boolean, default: false },
  placement: { type: String, default: 'bottom-start' },
  width: { type: Number, default: 240 }
})

defineEmits(['clear'])
</script>

<style>
.column-header-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
}

.column-header-filter__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-header-filter__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  font-size: 13px;
}

.column-header-filter__trigger:hover {
  background: var(--el-fill-color);
  color: var(--el-color-primary);
}

.column-header-filter__trigger.is-active {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 0 0 2px #bfdbfe;
}

.column-header-filter__trigger.is-active:hover {
  background: #1d4ed8;
  color: #fff;
}

.column-header-filter-popover .column-header-filter__content {
  display: grid;
  gap: 10px;
  max-height: min(480px, calc(100vh - 120px));
  overflow-y: auto;
}

.column-header-filter-popover .column-header-filter__group-label {
  margin-bottom: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.column-header-filter-popover .column-header-filter__footer {
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  text-align: right;
}

.column-header-filter-popover {
  max-width: calc(100vw - 32px) !important;
}
</style>
