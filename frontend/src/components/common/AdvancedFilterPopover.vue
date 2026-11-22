<template>
  <el-popover title="高级筛选" retain-on-selection :draft-filter="false"
    v-model:visible="visibleModel"
    trigger="click"
    placement="bottom-end"
    :width="popoverWidth"
    :popper-class="['common-advanced-filter-popover', compact ? 'is-compact' : '', popperClass].filter(Boolean).join(' ')"
  >
    <template #reference>
      <span ref="referenceHost" class="advanced-filter-reference"><slot name="reference">
        <el-button>
          高级筛选<span v-if="count" class="advanced-filter-count">（{{ count }}）</span>
        </el-button>
      </slot></span>
    </template>

    <div class="advanced-filter-shell" data-auto-draft="off">
      <div class="advanced-filter-header">
        <div class="advanced-filter-status">
          <span class="advanced-filter-badge" :class="{ 'is-active': count > 0 }">
            已启用 {{ count }} 项
          </span>
          <span class="advanced-filter-hint">多条件按「且」组合筛选</span>
        </div>
        <div class="advanced-filter-actions">
          <el-button v-if="count" type="primary" link @click="clearFilters">清空高级条件</el-button>
          <el-button link @click="cancelFilters">取消筛选</el-button>
          <el-button @click="visibleModel = false">关闭</el-button>
          <el-button type="primary" @click="confirm">确定</el-button>
        </div>
      </div>
      <div class="advanced-filter-body" :class="{ 'is-compact': compact }">
        <FilterDraftScope ref="draftScope">
          <AdvancedFilterFieldSearch :active="visible" :anchor="referenceHost" :scope="popperClass"><slot /></AdvancedFilterFieldSearch>
        </FilterDraftScope>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import FilterDraftScope from './FilterDraftScope'
import AdvancedFilterFieldSearch from './AdvancedFilterFieldSearch.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
  popperClass: { type: String, default: '' },
  compact: { type: Boolean, default: true },
})

const emit = defineEmits(['update:visible', 'clear', 'reset'])
const referenceHost=ref()
const draftScope=ref()
function confirm(){draftScope.value?.apply();visibleModel.value=false}
function cancelFilters(){draftScope.value?.discard();emit('reset');visibleModel.value=false}
function clearFilters(){draftScope.value?.discard();emit('clear')}

const visibleModel = computed({
  get: () => props.visible,
  // 隐藏面板保留条件；重置和清空仅由对应按钮显式触发。
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
  gap: 12px;
  padding: 9px 16px;
  background: var(--color-page-bg, #f8fafc);
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}

.advanced-filter-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.advanced-filter-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-sm, 6px);
  background: var(--color-surface-muted, #f1f5f9);
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.advanced-filter-badge.is-active {
  background: #e2e8f0;
  color: var(--color-primary-hover, #1e293b);
  font-weight: 600;
}

.advanced-filter-hint {
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
  white-space: nowrap;
}

.advanced-filter-actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
}

.advanced-filter-actions .el-button {
  min-height: 28px;
  height: 28px;
  margin-left: 0;
  padding: 4px 12px;
  font-size: 13px;
}

.advanced-filter-actions .el-button.is-link {
  padding: 2px 4px;
}

.advanced-filter-body {
  flex: 1;
  min-height: 0;
  max-height: min(560px, calc(100vh - 120px));
  padding: 12px 16px 14px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}

.advanced-filter-body.is-compact {
  padding: 10px 16px 14px;
}

:global(.common-advanced-filter-popover .app-window-popover__body) {
  padding: 0;
}

:global(.common-advanced-filter-popover.is-compact) {
  padding: 0 !important;
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
