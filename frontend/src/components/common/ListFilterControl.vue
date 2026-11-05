<template>
  <el-input
    v-if="definition.type === 'text'"
    :model-value="modelValue"
    :placeholder="definition.placeholder || `筛选${definition.label}`"
    clearable
    size="small"
    @update:model-value="update"
    @input="$emit('text-input', $event)"
    @keyup.enter="$emit('enter')"
  />
  <el-select
    v-else-if="definition.type === 'select' || definition.type === 'boolean'"
    :model-value="modelValue"
    :multiple="definition.multiple !== false && definition.type !== 'boolean'"
    :filterable="definition.filterable !== false"
    clearable
    collapse-tags
    collapse-tags-tooltip
    :max-collapse-tags="1"
    :placeholder="definition.placeholder || '全部'"
    size="small"
    @update:model-value="update"
    @change="$emit('change', $event)"
  >
    <el-option
      v-for="option in resolvedOptions"
      :key="String(option.value)"
      :label="option.label"
      :value="option.value"
    />
  </el-select>
  <div v-else-if="definition.type === 'date-range'" ref="dateRangeRef" class="list-filter-date-range">
    <el-date-picker
      :append-to="datePickerTarget"
      :popper-options="datePickerTarget ? datePickerPopperOptions : undefined"
      :model-value="modelValue"
      type="daterange"
      value-format="YYYY-MM-DD"
      range-separator="至"
      start-placeholder="开始"
      end-placeholder="结束"
      unlink-panels
      clearable
      size="small"
      @update:model-value="update"
      @change="$emit('change', $event)"
    />
  </div>
  <div v-else-if="definition.type === 'number-range'" class="list-filter-number-range">
    <el-input-number
      :model-value="rangeValue[0]"
      :controls="false"
      :min="definition.min"
      :max="definition.max"
      :precision="definition.precision"
      placeholder="最小"
      size="small"
      @update:model-value="updateRange(0, $event)"
      @change="changeRange(0, $event)"
    />
    <span>—</span>
    <el-input-number
      :model-value="rangeValue[1]"
      :controls="false"
      :min="definition.min"
      :max="definition.max"
      :precision="definition.precision"
      placeholder="最大"
      size="small"
      @update:model-value="updateRange(1, $event)"
      @change="changeRange(1, $event)"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean, Array, Object], default: '' },
  definition: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue', 'text-input', 'change', 'enter'])

const dateRangeRef = ref()
// 保留面板的传送与定位能力，但挂载到所属浮窗根节点，避免翻月被判定为外部点击。
// 不挂到内部滚动区，防止日期面板被裁切；非浮窗场景沿用默认挂载位置。
const datePickerTarget = computed(() => dateRangeRef.value?.closest('.el-popover') || undefined)
// 以视口为边界翻转和避让，固定定位避免被所属浮窗的 overflow 裁切。
const datePickerPopperOptions = {
  strategy: 'fixed',
  modifiers: [
    { name: 'flip', options: { boundary: 'viewport' } },
    { name: 'preventOverflow', options: { boundary: 'viewport' } },
  ],
}

const resolvedOptions = computed(() => {
  if (props.definition.type === 'boolean') {
    return props.definition.options || [
      { label: '是', value: true },
      { label: '否', value: false },
    ]
  }
  const source = typeof props.definition.options === 'function'
    ? props.definition.options()
    : props.definition.options
  return (source || []).map((option) => (
    option && typeof option === 'object'
      ? { label: option.label ?? option.name ?? String(option.value ?? option.id), value: option.value ?? option.id }
      : { label: String(option), value: option }
  ))
})

const rangeValue = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [null, null])
const update = (value) => emit('update:modelValue', value)
const updateRange = (index, value) => {
  const next = [...rangeValue.value]
  next[index] = value
  emit('update:modelValue', next)
}
const changeRange = (index, value) => {
  const next = [...rangeValue.value]
  next[index] = value
  emit('change', next)
}
</script>

<style scoped>
.el-select,
.el-date-editor {
  width: 100% !important;
}

.list-filter-number-range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 4px;
}

.list-filter-number-range .el-input-number {
  width: 100%;
}
</style>
