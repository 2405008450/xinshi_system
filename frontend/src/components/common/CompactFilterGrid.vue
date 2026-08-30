<template>
  <div class="compact-filter-grid">
    <label
      v-for="definition in fields"
      :key="definition.key"
      class="compact-filter-cell"
      :class="{ 'is-wide': definition.wide }"
    >
      <span class="compact-filter-cell__label">{{ definition.label }}</span>
      <ListFilterControl
        :model-value="model[definition.key]"
        :definition="definition"
        @update:model-value="update(definition.key, $event)"
        @text-input="$emit('text-input', definition, $event)"
        @change="$emit('change', definition, $event)"
        @enter="$emit('enter', definition)"
      />
    </label>
  </div>
</template>

<script setup>
import ListFilterControl from './ListFilterControl.vue'

defineProps({
  fields: { type: Array, default: () => [] },
  model: { type: Object, required: true },
})

const emit = defineEmits(['update', 'text-input', 'change', 'enter'])
const update = (key, value) => emit('update', key, value)
</script>

<style scoped>
.compact-filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.compact-filter-cell {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.compact-filter-cell.is-wide {
  grid-column: span 2;
}

.compact-filter-cell__label {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 760px) {
  .compact-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .compact-filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .compact-filter-cell.is-wide {
    grid-column: span 1;
  }
}
</style>
