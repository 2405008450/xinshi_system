<template>
  <el-popover
    v-model:visible="visibleModel"
    trigger="click"
    placement="bottom-end"
    :width="popoverWidth"
    :popper-class="['common-advanced-filter-popover', compact ? 'is-compact' : '', popperClass].filter(Boolean).join(' ')"
  >
    <template #reference>
      <slot name="reference">
        <el-button>
          高级筛选<span v-if="count" class="advanced-filter-count">（{{ count }}）</span>
        </el-button>
      </slot>
    </template>

    <div class="advanced-filter-shell">
      <div class="advanced-filter-header">
        <span class="advanced-filter-title">高级筛选</span>
        <div class="advanced-filter-actions">
          <el-button type="primary" link @click="$emit('reset')">重置</el-button>
          <el-button v-if="count" type="primary" link @click="$emit('clear')">清空高级条件</el-button>
          <el-button link @click="visibleModel = false">关闭</el-button>
        </div>
      </div>
      <div class="advanced-filter-body" :class="{ 'is-compact': compact }">
        <slot />
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
  popperClass: { type: String, default: '' },
  compact: { type: Boolean, default: true },
})

const emit = defineEmits(['update:visible', 'clear', 'reset'])

const visibleModel = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const popoverWidth = 'min(760px, calc(100vw - 32px))'
</script>

<style scoped>
.advanced-filter-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: calc(100vh - 32px);
  overflow: hidden;
}

.advanced-filter-header {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.advanced-filter-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.advanced-filter-actions {
  display: flex;
  flex: none;
  align-items: center;
}

.advanced-filter-body {
  flex: 1;
  min-height: 0;
  max-height: min(560px, calc(100vh - 120px));
  padding-top: 16px;
  overflow-y: auto;
  overflow-x: hidden;
}

.advanced-filter-body.is-compact {
  padding-top: 12px;
}

:global(.common-advanced-filter-popover.is-compact) {
  padding: 12px !important;
}

.advanced-filter-count {
  margin-left: 2px;
}

@media (max-width: 640px) {
  .advanced-filter-header {
    gap: 8px;
  }

  .advanced-filter-actions {
    gap: 0;
  }
}
</style>
