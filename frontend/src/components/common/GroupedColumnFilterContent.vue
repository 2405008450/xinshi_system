<template>
  <div class="grouped-column-filter">
    <div class="grouped-column-filter__body">
      <p class="grouped-column-filter__hint">点击“确定”应用筛选，关闭窗口可保留待确认的输入。</p>
      <div v-for="field in definition.fields" :key="field.key" class="grouped-column-filter__field">
        <div class="grouped-column-filter__label">{{ field.groupLabel || field.label }}</div>
        <template v-if="isMultiple(field)">
          <div v-if="supportsBlankFilter(field)" class="grouped-column-filter__blank" :class="{ 'is-active': isBlankFilter(drafts[field.key]) }">
            <el-checkbox :model-value="isBlankFilter(drafts[field.key])" @change="drafts[field.key] = $event ? BLANK_FILTER_VALUE : []">空</el-checkbox>
            <span class="grouped-column-filter__blank-hint">仅匹配未填写项</span>
          </div>
          <div v-if="!isBlankFilter(drafts[field.key])" class="grouped-column-filter__selection-actions">
            <span>已选 {{ drafts[field.key]?.length || 0 }} 项</span>
            <div class="grouped-column-filter__selection-buttons">
              <el-button link type="primary" size="small" @click="selectAll(field)">{{ keywords[field.key] ? '全选结果' : '全选' }}</el-button>
              <el-button link size="small" @click="drafts[field.key] = []">清空</el-button>
            </div>
          </div>
          <el-input v-if="!isBlankFilter(drafts[field.key]) && options(field).length > 8 && field.filterable !== false" v-model="keywords[field.key]" :prefix-icon="Search" :placeholder="`搜索${field.label}`" clearable size="small" class="grouped-column-filter__search" />
          <el-checkbox-group v-if="!isBlankFilter(drafts[field.key])" v-model="drafts[field.key]" class="grouped-column-filter__options">
            <el-checkbox v-for="option in filteredOptions(field)" :key="String(option.value)" :value="option.value">{{ option.label }}</el-checkbox>
          </el-checkbox-group>
        </template>
        <ListFilterControl v-else :definition="field" :model-value="drafts[field.key]"
          @update:model-value="value => drafts[field.key] = value" @enter="confirm" />
      </div>
    </div>
    <div class="grouped-column-filter__footer">
      <el-button link size="small" @click="clearGroup">清除本组筛选</el-button>
      <div class="grouped-column-filter__footer-actions">
        <el-button v-if="hasSelections" size="small" @click="$emit('cancel')">取消</el-button>
        <el-button v-else size="small" @click="$emit('close')">关闭</el-button>
        <el-button type="primary" size="small" @click="confirm">确定</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { matchesSearch } from '@/utils/searchMatching'

import { computed, reactive, watch } from 'vue'
import ListFilterControl from './ListFilterControl.vue'
import { BLANK_FILTER_VALUE, emptyFilterValue, isBlankFilter, supportsBlankFilter } from '@/utils/listFieldFilters'

const props = defineProps({ definition: { type: Object, required: true }, model: { type: Object, required: true } })
const emit = defineEmits(['update-field', 'text-input', 'change', 'enter', 'clear', 'close', 'cancel'])
const drafts = reactive({})
const keywords = reactive({})
const isMultiple = field => field.type === 'select' && field.multiple !== false
const hasSelections = computed(() => props.definition.fields.some(isMultiple))
const applied = computed(() => props.definition.fields.map(field => props.model[field.key] ?? emptyFilterValue(field)))
watch(() => JSON.stringify(applied.value), (current, previous) => {
  const oldValues = previous ? JSON.parse(previous) : []
  JSON.parse(current).forEach((value, index) => {
    if (JSON.stringify(value) !== JSON.stringify(oldValues[index])) {
      drafts[props.definition.fields[index].key] = value
    }
  })
}, { immediate: true })
const options = field => {
  const values = typeof field.options === 'function' ? field.options() : field.options
  return (values || []).map(item => item && typeof item === 'object'
    ? { label: item.label ?? item.name ?? String(item.value ?? item.id), value: item.value ?? item.id }
    : { label: String(item), value: item })
}
const filteredOptions = field => options(field).filter(item => matchesSearch(item.label, keywords[field.key]))
const selectAll = field => { drafts[field.key] = [...new Set([...(drafts[field.key] || []), ...filteredOptions(field).map(item => item.value)])] }
const confirm = () => {
  props.definition.fields.forEach(field => emit('update-field', field.key, Array.isArray(drafts[field.key]) ? [...drafts[field.key]] : drafts[field.key]))
  emit('enter')
  emit('close')
}
const clearGroup = () => {
  props.definition.fields.forEach(field => {
    emit('update-field', field.key, emptyFilterValue(field))
    drafts[field.key] = emptyFilterValue(field)
    keywords[field.key] = ''
  })
  emit('clear')
}
</script>

<style scoped>
.grouped-column-filter {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
  max-height: min(480px, calc(100vh - 130px));
}
.grouped-column-filter__body {
  display: grid;
  flex: 1;
  min-height: 0;
  gap: 10px;
  padding: 12px 14px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}
.grouped-column-filter__hint {
  margin: 0;
  padding: 6px 10px;
  border-radius: var(--radius-sm, 6px);
  background: var(--color-page-bg, #f8fafc);
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
  line-height: 1.45;
}
.grouped-column-filter__field {
  display: grid;
  gap: 6px;
}
.grouped-column-filter__label {
  color: var(--color-text-primary, #111827);
  font-size: 13px;
  font-weight: 600;
}
.grouped-column-filter__blank {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--color-page-bg, #f8fafc);
}
.grouped-column-filter__blank.is-active {
  border-color: #94a3b8;
  background: var(--color-surface-muted, #f1f5f9);
}
.grouped-column-filter__blank :deep(.el-checkbox) { height: 22px; margin-right: 0; }
.grouped-column-filter__blank-hint { color: var(--color-text-muted, #64748b); font-size: 12px; }
.grouped-column-filter__selection-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
}
.grouped-column-filter__selection-buttons { display: inline-flex; align-items: center; gap: 6px; }
.grouped-column-filter__selection-buttons .el-button { height: 22px; min-height: 22px; padding: 0 2px; margin-left: 0; }
.grouped-column-filter__options {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 180px;
  padding: 4px;
  overflow-y: auto;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--color-surface, #ffffff);
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}
.grouped-column-filter__options :deep(.el-checkbox) {
  width: 100%;
  height: auto;
  min-height: 30px;
  margin-right: 0;
  padding: 3px 8px;
  border-radius: var(--radius-sm, 6px);
}
.grouped-column-filter__options :deep(.el-checkbox:hover) { background: var(--color-page-bg, #f8fafc); }
.grouped-column-filter__options :deep(.el-checkbox.is-checked) { background: var(--color-surface-muted, #f1f5f9); }
.grouped-column-filter__footer {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 14px;
  background: var(--color-page-bg, #f8fafc);
  border-top: 1px solid var(--color-border, #e2e8f0);
}
.grouped-column-filter__footer-actions { display: inline-flex; align-items: center; gap: 6px; }
.grouped-column-filter__footer .el-button { min-height: 28px; height: 28px; margin-left: 0; padding: 4px 10px; font-size: 12px; }
.grouped-column-filter__footer .el-button.is-link { padding: 0 4px; color: var(--color-text-muted, #64748b); }
.grouped-column-filter__footer .el-button.is-link:hover { color: var(--color-primary, #334155); }
</style>
