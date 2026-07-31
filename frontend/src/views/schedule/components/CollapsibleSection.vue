<template>
  <section class="collapsible-section" :class="{ 'is-collapsed': !expanded }">
    <div
      class="collapsible-section__header"
      role="button"
      tabindex="0"
      :aria-expanded="expanded"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <div class="collapsible-section__heading">
        <span class="collapsible-section__title">{{ title }}</span>
        <span v-if="subtitle" class="collapsible-section__subtitle">{{ subtitle }}</span>
        <slot name="badge" />
      </div>
      <div class="collapsible-section__header-actions" @click.stop @keydown.stop>
        <slot name="actions" />
        <el-button
          text
          circle
          class="collapsible-section__toggle"
          :aria-label="expanded ? `收起${title}` : `展开${title}`"
          @click="toggle"
        >
          <el-icon :class="{ 'is-expanded': expanded }"><ArrowDown /></el-icon>
        </el-button>
      </div>
    </div>

    <el-collapse-transition>
      <div v-show="expanded" class="collapsible-section__body">
        <slot />
      </div>
    </el-collapse-transition>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  storageKey: { type: String, required: true },
  defaultOpen: { type: Boolean, default: true }
})

const STORAGE_PREFIX = 'workbench_section_'

function readInitialState() {
  try {
    const stored = localStorage.getItem(`${STORAGE_PREFIX}${props.storageKey}`)
    if (stored !== null) return stored === '1'
  } catch {}
  return props.defaultOpen
}

const expanded = ref(readInitialState())

function toggle() {
  expanded.value = !expanded.value
}

watch(expanded, (value) => {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${props.storageKey}`, value ? '1' : '0')
  } catch {}
})
</script>

<style scoped>
.collapsible-section {
  margin-bottom: 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
  overflow: hidden;
}

.collapsible-section__header {
  min-height: 44px;
  padding: 0 12px 0 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--el-fill-color-lighter);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;
}

.collapsible-section__header:hover {
  background: var(--el-fill-color-light);
}

.collapsible-section__header:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}

.collapsible-section__heading {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.collapsible-section__title {
  flex: none;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.collapsible-section__subtitle {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.collapsible-section__toggle {
  flex: none;
}

.collapsible-section__header-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapsible-section__toggle .el-icon {
  transition: transform 0.2s ease;
}

.collapsible-section__toggle .el-icon.is-expanded {
  transform: rotate(180deg);
}

.collapsible-section__body {
  padding: 12px 14px 14px;
}

.is-collapsed .collapsible-section__header {
  border-bottom: 0;
}

@media (max-width: 720px) {
  .collapsible-section__subtitle {
    display: none;
  }

  .collapsible-section__body {
    padding: 10px;
  }

  .collapsible-section__header-actions :deep(.el-input) {
    display: none;
  }
}
</style>
