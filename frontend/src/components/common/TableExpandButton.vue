<template>
  <button
    type="button"
    class="table-expand-button"
    :class="{ 'is-expanded': expanded, 'has-count': hasCount }"
    :aria-label="expanded ? collapseLabel : expandLabel"
    :aria-expanded="expanded"
    :title="hasCount ? `${expanded ? collapseLabel : expandLabel}（${count}）` : undefined"
    @click.stop="emit('click')"
  >
    <svg class="table-expand-button__icon" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
      <path d="M3 1.5 6.5 5 3 8.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <span v-if="hasCount" class="table-expand-button__count">{{ count }}</span>
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  expanded: { type: Boolean, default: false },
  count: { type: Number, default: null },
  expandLabel: { type: String, default: '展开详情' },
  collapseLabel: { type: String, default: '收起详情' }
})

const emit = defineEmits(['click'])
const hasCount = computed(() => Number.isFinite(props.count))
</script>

<style scoped>
.table-expand-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-width: 20px;
  height: 20px;
  padding: 0 4px;
  border: 0;
  border-radius: 10px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  flex: 0 0 auto;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.table-expand-button.has-count {
  padding: 0 6px 0 4px;
}

.table-expand-button:hover {
  background: var(--el-color-primary-light-8);
}

.table-expand-button__icon {
  width: 10px;
  height: 10px;
  transform: rotate(0deg);
  transition: transform 0.2s ease;
}

.table-expand-button.is-expanded {
  background: var(--el-color-primary);
  color: #fff;
}

.table-expand-button.is-expanded:hover {
  background: var(--el-color-primary-dark-2);
}

.table-expand-button.is-expanded .table-expand-button__icon {
  transform: rotate(90deg);
}

.table-expand-button__count {
  font-variant-numeric: tabular-nums;
}

.table-expand-button:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 1px;
}

@media (prefers-reduced-motion: reduce) {
  .table-expand-button,
  .table-expand-button__icon {
    transition: none;
  }
}
</style>
