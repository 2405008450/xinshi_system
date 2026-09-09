<template>
  <ColumnHeaderFilter
    ref="popoverRef"
    :label="definition.label"
    :active="active"
    :width="definition.headerWidth || (definition.wide ? 320 : 240)"
    :placement="placement"
    :hide-default-footer="usesConfirmedSelection"
    @before-enter="prepareDraft"
    @clear="clear"
  >
    <template #label><slot name="label">{{ definition.label }}</slot></template>
    <div v-if="usesConfirmedSelection" class="confirmed-header-filter">
      <div class="confirmed-header-filter__header">
        <span>选择{{ definition.label }}</span>
        <div>
          <el-button link type="primary" size="small" @click="selectAll">{{ filterKeyword ? '全选结果' : '全选' }}</el-button>
          <el-button link size="small" :disabled="!draftValue.length" @click="draftValue = []">清空</el-button>
        </div>
      </div>
      <el-input
        v-if="resolvedOptions.length > 8 && definition.filterable !== false"
        v-model="filterKeyword"
        class="confirmed-header-filter__search"
        :placeholder="`搜索${definition.label}`"
        clearable
        size="small"
      />
      <el-checkbox-group v-model="draftValue" class="confirmed-header-filter__options">
        <el-checkbox v-for="option in filteredOptions" :key="String(option.value)" :value="option.value">
          {{ option.label }}
        </el-checkbox>
        <el-empty v-if="!filteredOptions.length" description="暂无匹配选项" :image-size="48" />
      </el-checkbox-group>
      <div class="confirmed-header-filter__footer">
        <span>已选 {{ draftValue.length }} 项</span>
        <div>
          <el-button size="small" @click="cancel">取消</el-button>
          <el-button type="primary" size="small" @click="confirm">确定</el-button>
        </div>
      </div>
    </div>
    <ListFilterControl
      v-else
      :model-value="modelValue"
      :definition="definition"
      @update:model-value="$emit('update:modelValue', $event)"
      @text-input="$emit('text-input', $event)"
      @change="$emit('change', $event)"
      @enter="$emit('enter')"
    />
  </ColumnHeaderFilter>
</template>

<script setup>
import { computed, ref } from 'vue'
import ColumnHeaderFilter from './ColumnHeaderFilter.vue'
import ListFilterControl from './ListFilterControl.vue'
import { emptyFilterValue, isActiveFilterValue } from '@/utils/listFieldFilters'

const props = defineProps({
  definition: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: '' },
  placement: { type: String, default: 'bottom-start' },
})

const emit = defineEmits(['update:modelValue', 'text-input', 'change', 'enter', 'clear'])
const active = computed(() => isActiveFilterValue(props.definition, props.modelValue))
// 所有可多选的表头选择筛选统一直接展示复选项，避免下拉选择后反复打开。
const usesConfirmedSelection = computed(() => props.definition.type === 'select' && props.definition.multiple !== false)
const popoverRef = ref()
const draftValue = ref([])
const filterKeyword = ref('')
const resolvedOptions = computed(() => {
  const source = typeof props.definition.options === 'function'
    ? props.definition.options()
    : props.definition.options
  return (source || []).map((option) => option && typeof option === 'object'
    ? { label: option.label ?? option.name ?? String(option.value ?? option.id), value: option.value ?? option.id }
    : { label: String(option), value: option })
})
const filteredOptions = computed(() => {
  const keyword = filterKeyword.value.trim().toLocaleLowerCase()
  if (!keyword) return resolvedOptions.value
  return resolvedOptions.value.filter((option) => String(option.label).toLocaleLowerCase().includes(keyword))
})
const prepareDraft = () => {
  draftValue.value = Array.isArray(props.modelValue) ? [...props.modelValue] : []
  filterKeyword.value = ''
}
const selectAll = () => {
  const selected = new Set(draftValue.value)
  filteredOptions.value.forEach((option) => selected.add(option.value))
  draftValue.value = [...selected]
}
const cancel = () => { prepareDraft(); popoverRef.value?.close() }
const confirm = () => {
  const next = [...draftValue.value]
  const current = Array.isArray(props.modelValue) ? props.modelValue : []
  const changed = next.length !== current.length || next.some((value, index) => value !== current[index])
  if (changed) {
    emit('update:modelValue', next)
    emit('change', next)
  }
  popoverRef.value?.close()
}
const clear = () => {
  emit('update:modelValue', emptyFilterValue(props.definition))
  emit('clear')
}
</script>

<style scoped>
.confirmed-header-filter{display:flex;max-height:min(440px,calc(100vh - 140px));flex-direction:column}.confirmed-header-filter__header,.confirmed-header-filter__footer{display:flex;flex:none;align-items:center;justify-content:space-between}.confirmed-header-filter__header{padding-bottom:8px;border-bottom:1px solid var(--el-border-color-lighter);font-weight:600}.confirmed-header-filter__header .el-button+.el-button,.confirmed-header-filter__footer .el-button+.el-button{margin-left:6px}.confirmed-header-filter__search{flex:none;margin-top:8px}.confirmed-header-filter__options{display:flex;min-height:0;padding:6px 0;overflow-y:auto;flex-direction:column}.confirmed-header-filter__options .el-checkbox{width:100%;height:30px;margin-right:0}.confirmed-header-filter__options .el-empty{padding:12px 0}.confirmed-header-filter__footer{padding-top:8px;border-top:1px solid var(--el-border-color-lighter);color:var(--el-text-color-secondary);font-size:12px}
</style>
