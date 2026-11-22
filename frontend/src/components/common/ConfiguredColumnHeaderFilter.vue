<template>
  <ColumnHeaderFilter
    ref="popoverRef"
    :label="definition.label"
    :active="active"
    :active-count="isGroup ? groupActiveCount : 0"
    :width="definition.headerWidth || (definition.wide ? 340 : (usesConfirmedSelection ? 320 : 296))"
    :placement="placement"
    hide-default-footer
    @clear="clear"
    @dismiss="discardDraft"
  >
    <template #label><slot name="label">{{ definition.label }}</slot></template>
    <GroupedColumnFilterContent
      v-if="isGroup"
      :key="groupOpenVersion"
      :definition="definition"
      :model="model"
      @update-field="(key, value) => $emit('update-field', key, value)"
      @text-input="$emit('text-input', $event)"
      @change="$emit('change')"
      @enter="$emit('enter')"
      @clear="$emit('clear')"
      @close="popoverRef?.close({ preserveDraft: true })"
      @cancel="popoverRef?.close()"
    />
    <div v-else-if="usesConfirmedSelection" class="confirmed-header-filter">
      <div class="confirmed-header-filter__body">
        <div class="confirmed-header-filter__toolbar">
          <span class="confirmed-header-filter__meta">
            {{ filterKeyword.trim() ? `匹配 ${filteredOptions.length} / ${resolvedOptions.length} 项` : `共 ${resolvedOptions.length} 项` }}
          </span>
          <div v-if="!blankSelected" class="confirmed-header-filter__quick-actions">
            <el-button link type="primary" size="small" @click="selectAll">{{ filterKeyword ? '全选结果' : '全选' }}</el-button>
            <span class="confirmed-header-filter__divider" aria-hidden="true" />
            <el-button link size="small" :disabled="!draftValue.length" @click="draftValue = []">清空</el-button>
          </div>
        </div>
        <el-input
          v-if="!blankSelected && resolvedOptions.length > 8 && definition.filterable !== false"
          v-model="filterKeyword"
          class="confirmed-header-filter__search"
          :prefix-icon="Search"
          :placeholder="`搜索${definition.label}`"
          clearable
          size="small"
        />
        <div
          v-if="supportsBlankFilter(definition)"
          class="filter-blank-row"
          :class="{ 'is-active': blankSelected }"
        >
          <el-checkbox :model-value="blankSelected" @change="draftValue = $event ? BLANK_FILTER_VALUE : []">空</el-checkbox>
          <span class="filter-blank-row__hint">仅匹配未填写项</span>
        </div>
        <div v-if="!blankSelected && selectedDraftOptions.length" class="confirmed-header-filter__selected-tags">
          <span
            v-for="item in selectedDraftOptions"
            :key="String(item.value)"
            class="confirmed-header-filter__chip"
            :title="item.label"
          >
            <span class="confirmed-header-filter__chip-text">{{ item.label }}</span>
            <button
              type="button"
              class="confirmed-header-filter__chip-close"
              :aria-label="`移除 ${item.label}`"
              @click.stop="removeSelected(item.value)"
            >×</button>
          </span>
        </div>
        <div v-if="!blankSelected" class="confirmed-header-filter__list-wrap">
          <el-checkbox-group v-model="draftValue" class="confirmed-header-filter__options">
            <el-checkbox v-for="option in filteredOptions" :key="String(option.value)" :value="option.value">
              {{ option.label }}
            </el-checkbox>
            <el-empty v-if="!filteredOptions.length" description="暂无匹配选项" :image-size="44" />
          </el-checkbox-group>
        </div>
      </div>
      <div class="confirmed-header-filter__footer">
        <span class="confirmed-header-filter__count" :class="{ 'is-active': blankSelected || draftValue.length > 0 }">
          已选 {{ blankSelected ? 1 : draftValue.length }} 项
        </span>
        <div class="confirmed-header-filter__footer-actions">
          <el-button link size="small" @click="clear">取消筛选</el-button>
          <el-button size="small" @click="cancel">取消</el-button>
          <el-button type="primary" size="small" @click="confirm">确定</el-button>
        </div>
      </div>
    </div>
    <div v-else class="single-header-filter">
      <div class="single-header-filter__body">
        <ListFilterControl
          :model-value="draftValue"
          :definition="definition"
          @update:model-value="draftValue = $event"
          @change="definition.applyOnChange && confirm()"
          @enter="confirm"
        />
      </div>
      <div class="confirmed-header-filter__footer single-header-filter__footer">
        <el-button link size="small" @click="clear">取消筛选</el-button>
        <div class="confirmed-header-filter__footer-actions">
          <el-button size="small" @click="cancel">取消</el-button>
          <el-button type="primary" size="small" @click="confirm">确定</el-button>
        </div>
      </div>
    </div>
  </ColumnHeaderFilter>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { matchesSearch } from '@/utils/searchMatching'

import { computed, ref, watch } from 'vue'
import ColumnHeaderFilter from './ColumnHeaderFilter.vue'
import ListFilterControl from './ListFilterControl.vue'
import GroupedColumnFilterContent from './GroupedColumnFilterContent.vue'
import { BLANK_FILTER_VALUE, countActiveFilters, emptyFilterValue, isActiveFilterValue, isBlankFilter, supportsBlankFilter } from '@/utils/listFieldFilters'

const props = defineProps({
  definition: { type: Object, required: true },
  model: { type: Object, default: () => ({}) },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: '' },
  placement: { type: String, default: 'bottom-start' },
})

const emit = defineEmits(['update:modelValue', 'update-field', 'text-input', 'change', 'enter', 'clear'])
const isGroup = computed(() => props.definition.type === 'group')
const groupActiveCount = computed(() => countActiveFilters(props.model, props.definition.fields || []))
const groupOpenVersion = ref(0)
const active = computed(() => isGroup.value ? groupActiveCount.value > 0 : isActiveFilterValue(props.definition, props.modelValue))
// 所有可多选的表头选择筛选统一直接展示复选项，避免下拉选择后反复打开。
const usesConfirmedSelection = computed(() => props.definition.type === 'select' && props.definition.multiple !== false)
const popoverRef = ref()
const draftValue = ref([])
const blankSelected = computed(() => isBlankFilter(draftValue.value))
const filterKeyword = ref('')
const resolvedOptions = computed(() => {
  const source = typeof props.definition.options === 'function'
    ? props.definition.options()
    : props.definition.options
  const seen = new Set()
  return (source || []).map((option) => option && typeof option === 'object'
    ? { label: option.label ?? option.name ?? String(option.value ?? option.id), value: option.value ?? option.id }
    : { label: String(option), value: option })
    .filter((option) => {
      if (seen.has(option.value)) return false
      seen.add(option.value)
      return true
    })
})
const filteredOptions = computed(() => {
  const keyword = filterKeyword.value.trim().toLocaleLowerCase()
  if (!keyword) return resolvedOptions.value
  return resolvedOptions.value.filter((option) => matchesSearch(option.label, keyword))
})
const selectedDraftOptions = computed(() => {
  if (!Array.isArray(draftValue.value) || !draftValue.value.length) return []
  const map = new Map(resolvedOptions.value.map((option) => [option.value, option.label]))
  return draftValue.value.map((value) => ({ value, label: map.get(value) ?? String(value) }))
})
const removeSelected = (value) => {
  if (!Array.isArray(draftValue.value)) return
  draftValue.value = draftValue.value.filter((item) => item !== value)
}
const discardDraft = () => {
  groupOpenVersion.value++
  draftValue.value = Array.isArray(props.modelValue) ? [...props.modelValue]
    : props.modelValue && typeof props.modelValue === 'object' ? { ...props.modelValue }
    : props.modelValue ?? emptyFilterValue(props.definition)
  if (usesConfirmedSelection.value && !Array.isArray(draftValue.value) && !isBlankFilter(draftValue.value)) draftValue.value = []
  filterKeyword.value = ''
}
watch(() => props.modelValue, discardDraft, { immediate: true, deep: true })
const selectAll = () => {
  const selected = new Set(draftValue.value)
  filteredOptions.value.forEach((option) => selected.add(option.value))
  draftValue.value = [...selected]
}
const cancel = () => popoverRef.value?.close()
const confirm = () => {
  const next = Array.isArray(draftValue.value) ? [...draftValue.value] : draftValue.value
  const current = props.modelValue
  const changed = JSON.stringify(next) !== JSON.stringify(current)
  if (changed) {
    emit('update:modelValue', next)
    emit('change', next)
  }
  filterKeyword.value = ''
  popoverRef.value?.close({ preserveDraft: true })
}
const clear = () => {
  const value = emptyFilterValue(props.definition)
  draftValue.value = value
  filterKeyword.value = ''
  emit('update:modelValue', value)
  emit('clear')
}
</script>

<style scoped>
.confirmed-header-filter,
.single-header-filter {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  max-height: min(460px, calc(100vh - 130px));
}

.confirmed-header-filter__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  gap: 8px;
  padding: 10px 12px 10px;
}

.single-header-filter__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
}

.confirmed-header-filter__toolbar {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.confirmed-header-filter__meta {
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
  line-height: 1.4;
}

.confirmed-header-filter__quick-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.confirmed-header-filter__quick-actions .el-button {
  height: 22px;
  min-height: 22px;
  padding: 0 2px;
  margin-left: 0;
  font-size: 12px;
}

.confirmed-header-filter__divider {
  width: 1px;
  height: 11px;
  background: var(--color-border, #e2e8f0);
}

.confirmed-header-filter__search {
  flex: none;
}

.confirmed-header-filter__search :deep(.el-input__wrapper) {
  min-height: 32px;
  border-radius: var(--radius-md, 8px);
  background: var(--color-page-bg, #f8fafc);
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.confirmed-header-filter__search :deep(.el-input__wrapper.is-focus),
.confirmed-header-filter__search :deep(.el-input__wrapper:hover) {
  background: var(--color-surface, #ffffff);
}

.filter-blank-row {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 10px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--color-page-bg, #f8fafc);
  transition: border-color 160ms ease, background-color 160ms ease;
}

.filter-blank-row:hover {
  border-color: #cbd5e1;
}

.filter-blank-row.is-active {
  border-color: #94a3b8;
  background: var(--color-surface-muted, #f1f5f9);
}

.filter-blank-row :deep(.el-checkbox) {
  height: 22px;
  margin-right: 0;
}

.filter-blank-row__hint {
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
}

.confirmed-header-filter__selected-tags {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  gap: 5px;
  max-height: 62px;
  padding: 6px 8px;
  overflow-y: auto;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--color-page-bg, #f8fafc);
}

.confirmed-header-filter__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 1px 6px 1px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: var(--color-surface, #ffffff);
  color: var(--color-text-primary, #111827);
  font-size: 12px;
  line-height: 20px;
}

.confirmed-header-filter__chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.confirmed-header-filter__chip-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted, #64748b);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  transition: background-color 140ms ease, color 140ms ease;
}

.confirmed-header-filter__chip-close:hover {
  background: var(--color-primary-soft, #e2e8f0);
  color: var(--color-text-primary, #111827);
}

.confirmed-header-filter__list-wrap {
  display: flex;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--color-surface, #ffffff);
  overflow: hidden;
}

.confirmed-header-filter__options {
  display: flex;
  flex: 1;
  min-height: 0;
  max-height: min(260px, calc(100vh - 300px));
  padding: 4px;
  overflow-y: auto;
  flex-direction: column;
  gap: 2px;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}

.confirmed-header-filter__options::-webkit-scrollbar,
.confirmed-header-filter__selected-tags::-webkit-scrollbar {
  width: 6px;
}

.confirmed-header-filter__options::-webkit-scrollbar-thumb,
.confirmed-header-filter__selected-tags::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: #cbd5e1;
}

.confirmed-header-filter__options::-webkit-scrollbar-thumb:hover,
.confirmed-header-filter__selected-tags::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.confirmed-header-filter__options :deep(.el-checkbox) {
  display: flex;
  align-items: center;
  width: 100%;
  height: auto;
  min-height: 32px;
  margin-right: 0;
  padding: 4px 8px;
  border-radius: var(--radius-sm, 6px);
  color: var(--color-text-secondary, #475569);
  transition: background-color 140ms ease, color 140ms ease;
}

.confirmed-header-filter__options :deep(.el-checkbox:hover) {
  background: var(--color-page-bg, #f8fafc);
  color: var(--color-text-primary, #111827);
}

.confirmed-header-filter__options :deep(.el-checkbox.is-checked) {
  background: var(--color-surface-muted, #f1f5f9);
}

.confirmed-header-filter__options :deep(.el-checkbox.is-checked .el-checkbox__label) {
  color: var(--color-text-primary, #111827);
  font-weight: 500;
}

.confirmed-header-filter__options :deep(.el-checkbox__label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.confirmed-header-filter__options .el-empty {
  padding: 18px 0;
}

.confirmed-header-filter__footer {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 12px;
  background: var(--color-page-bg, #f8fafc);
  border-top: 1px solid var(--color-border, #e2e8f0);
}

.confirmed-header-filter__count {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--color-surface-muted, #f1f5f9);
  color: var(--color-text-muted, #64748b);
  font-size: 12px;
  line-height: 18px;
}

.confirmed-header-filter__count.is-active {
  background: var(--color-primary-soft, #e2e8f0);
  color: var(--color-primary, #334155);
  font-weight: 500;
}

.confirmed-header-filter__footer-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.confirmed-header-filter__footer .el-button {
  min-height: 28px;
  height: 28px;
  margin-left: 0;
  padding: 4px 10px;
  font-size: 12px;
}

.confirmed-header-filter__footer .el-button.is-link {
  padding: 0 4px;
  color: var(--color-text-muted, #64748b);
}

.confirmed-header-filter__footer .el-button.is-link:hover {
  color: var(--color-primary, #334155);
}
</style>
