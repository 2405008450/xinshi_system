<template>
  <button
    type="button"
    class="table-expand-button"
    :class="{ 'is-expanded': expanded }"
    :aria-label="expanded ? collapseLabel : expandLabel"
    :aria-expanded="expanded"
    @click.stop="emit('click')"
  >
    <span aria-hidden="true">›</span>
  </button>
</template>

<script setup>
defineProps({
  expanded: { type: Boolean, default: false },
  expandLabel: { type: String, default: '展开详情' },
  collapseLabel: { type: String, default: '收起详情' }
})

const emit = defineEmits(['click'])
</script>

<style scoped>
.table-expand-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  flex: 0 0 auto;
}

.table-expand-button:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.table-expand-button span {
  display: block;
  font-size: 20px;
  line-height: 1;
  transform: rotate(0deg);
  transition: transform 0.2s ease;
}

.table-expand-button.is-expanded span {
  transform: rotate(90deg);
}

.table-expand-button:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 1px;
}
</style>
