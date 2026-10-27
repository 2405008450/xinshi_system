<template>
<div class="project-column-header">
            <ConfiguredColumnHeaderFilter
              v-if="context.headerFilterDefinition(column.key)"
              :definition="context.headerFilterDefinition(column.key)"
              :model-value="context.searchForm[context.headerFilterDefinition(column.key).key]"
              @update:model-value="context.searchForm[context.headerFilterDefinition(column.key).key] = $event"
              @text-input="context.handleConfiguredTextInput"
              @change="context.handleSearch"
              @enter="context.handleSearch"
              @clear="context.handleSearch"
            >
              <template #label>
                <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
                <span v-else>{{ column.label }}</span>
              </template>
            </ConfiguredColumnHeaderFilter>
            <template v-else>
              <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
              <span v-else>{{ column.label }}</span>
            </template>
            <button
              v-if="context.getTimeSortMode(column.key)"
              type="button"
              class="time-column-sort-trigger"
              :class="{ 'is-active': context.isTimeSortActive(column.key) }"
              :aria-label="context.getTimeSortTitle(column)"
              :aria-pressed="context.isTimeSortActive(column.key)"
              :title="context.getTimeSortTitle(column)"
              :data-sort-field="column.key"
              :data-sort-direction="context.getSortDirection(column.key)"
              @click.stop="context.toggleTimeSort(column.key)"
            >
              <el-icon><SortDown v-if="context.getSortDirection(column.key)==='descending'" /><SortUp v-else-if="context.getSortDirection(column.key)==='ascending'" /><Sort v-else /></el-icon>
            </button>
          </div>
</template>
<script setup>
import {SortUp,SortDown,Sort} from '@element-plus/icons-vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
defineProps({column:{type:Object,required:true},context:{type:Object,required:true}})
</script>
<style scoped>
.project-column-header { display: inline-flex; align-items: center; max-width: 100%; gap: 4px; }
.time-column-sort-trigger {
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
.time-column-sort-trigger:hover { background: var(--el-fill-color); color: var(--el-color-primary); }
.time-column-sort-trigger.is-active {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 0 0 2px var(--color-primary-soft);
}
.time-column-sort-trigger.is-active:hover { background: var(--color-primary-hover); color: #fff; }

</style>
