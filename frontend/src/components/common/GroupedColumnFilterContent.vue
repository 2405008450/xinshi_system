<template>
  <div class="grouped-column-filter">
    <p class="grouped-column-filter__hint">不同条件同时满足。文本自动查询；多选勾选后点击“确定”。</p>
    <div v-for="field in definition.fields" :key="field.key" class="grouped-column-filter__field">
      <div class="grouped-column-filter__label">{{ field.groupLabel || field.label }}</div>
      <template v-if="isMultiple(field)">
        <div class="grouped-column-filter__selection-actions">
          <span>已选 {{ drafts[field.key]?.length || 0 }} 项</span>
          <el-button link type="primary" size="small" @click="selectAll(field)">{{ keywords[field.key] ? '全选结果' : '全选' }}</el-button>
          <el-button link size="small" @click="drafts[field.key] = []">清空</el-button>
        </div>
        <el-input v-if="options(field).length > 8 && field.filterable !== false" v-model="keywords[field.key]" :placeholder="`搜索${field.label}`" clearable size="small" />
        <el-checkbox-group v-model="drafts[field.key]" class="grouped-column-filter__options">
          <el-checkbox v-for="option in filteredOptions(field)" :key="String(option.value)" :value="option.value">{{ option.label }}</el-checkbox>
        </el-checkbox-group>
      </template>
      <ListFilterControl v-else :definition="field" :model-value="model[field.key]"
        @update:model-value="value => $emit('update-field', field.key, value)"
        @text-input="$emit('text-input', $event)" @change="$emit('change')" @enter="$emit('enter')" />
    </div>
    <div class="grouped-column-filter__footer">
      <el-button link type="primary" size="small" @click="clearGroup">清除本组筛选</el-button>
      <div>
        <el-button size="small" @click="$emit('close')">{{ hasSelections ? '取消' : '关闭' }}</el-button>
        <el-button type="primary" size="small" @click="confirm">{{ hasSelections ? '确定' : '查询' }}</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import ListFilterControl from './ListFilterControl.vue'
import { emptyFilterValue } from '@/utils/listFieldFilters'

const props = defineProps({ definition: { type: Object, required: true }, model: { type: Object, required: true } })
const emit = defineEmits(['update-field', 'text-input', 'change', 'enter', 'clear', 'close'])
const drafts = reactive({})
const keywords = reactive({})
const isMultiple = field => field.type === 'select' && field.multiple !== false
const hasSelections = computed(() => props.definition.fields.some(isMultiple))
// 外部重置或高级筛选修改后同步正式值；未确认的勾选不会写入页面条件。
watch(() => props.definition.fields.filter(isMultiple).map(field => [field.key, props.model[field.key]]), values => {
  values.forEach(([key, value]) => { drafts[key] = [...(value || [])] })
}, { immediate: true, deep: true })
const options = field => {
  const values = typeof field.options === 'function' ? field.options() : field.options
  return (values || []).map(item => item && typeof item === 'object'
    ? { label: item.label ?? item.name ?? String(item.value ?? item.id), value: item.value ?? item.id }
    : { label: String(item), value: item })
}
const filteredOptions = field => options(field).filter(item => String(item.label).toLocaleLowerCase().includes((keywords[field.key] || '').trim().toLocaleLowerCase()))
const selectAll = field => { drafts[field.key] = [...new Set([...(drafts[field.key] || []), ...filteredOptions(field).map(item => item.value)])] }
const confirm = () => {
  props.definition.fields.filter(isMultiple).forEach(field => emit('update-field', field.key, [...(drafts[field.key] || [])]))
  emit('enter')
  emit('close')
}
const clearGroup = () => {
  props.definition.fields.forEach(field => {
    emit('update-field', field.key, emptyFilterValue(field))
    if (isMultiple(field)) drafts[field.key] = []
    keywords[field.key] = ''
  })
  emit('clear')
}
</script>

<style scoped>
.grouped-column-filter { display: grid; gap: 12px; min-width: 0; }
.grouped-column-filter__hint { margin: 0; color: var(--el-text-color-secondary); font-size: 12px; }
.grouped-column-filter__label { margin-bottom: 6px; font-weight: 600; }
.grouped-column-filter__selection-actions { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.grouped-column-filter__options { display: flex; flex-wrap: wrap; max-height: 180px; overflow-y: auto; }
.grouped-column-filter__options .el-checkbox { margin-right: 12px; height: 28px; }
.grouped-column-filter__footer { position: sticky; bottom: -1px; z-index: 1; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 10px 0 2px; background: var(--el-bg-color-overlay); border-top: 1px solid var(--el-border-color-lighter); }
</style>
