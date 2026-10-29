<template>
  <el-popover
    trigger="click"
    placement="bottom-end"
    :width="secondaryColumns.length ? 620 : (columnCount > 1 ? 520 : 280)"
    popper-class="table-column-settings-popover"
    @hide="searchKeyword = ''"
  >
    <template #reference>
      <el-button>字段设置</el-button>
    </template>
    <div ref="settingsRoot" class="column-settings">
      <div class="column-settings__section-header">
        <div>
          <div class="column-settings__section-title">{{ title }}</div>
          <div class="column-settings__summary">
            <span>可选字段 {{ columns.length }} 项</span>
            <span>已选择 {{ modelValue.length }} 项</span>
          </div>
        </div>
        <ColumnDefaultActions :settings-key="settingsKey" :title="title" :columns="columns" :selected-keys="modelValue" @apply="$emit('update:modelValue', $event)" @reset="reset(false)" />
      </div>
      <div class="column-settings__search">
        <el-input v-model="searchKeyword" clearable placeholder="搜索字段名称，支持多个关键词" aria-label="搜索字段名称" :prefix-icon="Search" />
      </div>
      <div v-if="hint" class="column-settings__hint">{{ hint }}</div>
      <div v-if="searchKeyword.trim()" class="column-settings__matches">匹配 {{ filteredColumns.length }} 项</div>
      <el-checkbox-group
        :model-value="modelValue"
        :style="{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }"
        @update:model-value="$emit('update:modelValue', $event)"
      >
        <div v-for="column in filteredColumns" :key="column.key" class="column-settings__item" :class="{ 'is-drop-target': dropKey === column.key && !dragSecondary }">
          <button type="button" class="column-settings__drag" :data-column-key="column.key" :data-secondary="false" draggable="false" :aria-label="`拖动排序：${column.label}`" title="拖动调整顺序；也可用上下方向键" @keydown.up.prevent="moveByKeyboard(column.key, -1, false)" @keydown.down.prevent="moveByKeyboard(column.key, 1, false)">⠿</button>
          <el-checkbox :value="column.key">{{ column.label }}</el-checkbox>
        </div>
      </el-checkbox-group>
      <div v-if="!filteredColumns.length" class="column-settings__empty">{{ searchKeyword.trim() ? '没有匹配的字段，请调整关键词' : '暂无可选字段' }}</div>

      <template v-if="secondaryColumns.length">
        <el-divider />
        <div class="column-settings__section-header">
          <div>
            <div class="column-settings__section-title">{{ secondaryTitle }}</div>
            <div class="column-settings__summary">
              <span>可选字段 {{ secondaryColumns.length }} 项</span>
              <span>已选择 {{ secondaryModelValue.length }} 项</span>
            </div>
          </div>
          <ColumnDefaultActions :settings-key="settingsKey" section="secondary" :title="secondaryTitle" :columns="secondaryColumns" :selected-keys="secondaryModelValue" @apply="$emit('update:secondaryModelValue', $event)" @reset="reset(true)" />
        </div>
        <div v-if="secondaryHint" class="column-settings__hint">{{ secondaryHint }}</div>
        <div v-if="searchKeyword.trim()" class="column-settings__matches">匹配 {{ filteredSecondaryColumns.length }} 项</div>
        <el-checkbox-group
          :model-value="secondaryModelValue"
          :style="{ gridTemplateColumns: `repeat(${secondaryColumnCount}, minmax(0, 1fr))` }"
          @update:model-value="$emit('update:secondaryModelValue', $event)"
        >
          <div v-for="column in filteredSecondaryColumns" :key="column.key" class="column-settings__item" :class="{ 'is-drop-target': dropKey === column.key && dragSecondary }">
            <button type="button" class="column-settings__drag" :data-column-key="column.key" :data-secondary="true" draggable="false" :aria-label="`拖动排序：${column.label}`" title="拖动调整顺序；也可用上下方向键" @keydown.up.prevent="moveByKeyboard(column.key, -1, true)" @keydown.down.prevent="moveByKeyboard(column.key, 1, true)">⠿</button>
            <el-checkbox :value="column.key">{{ column.label }}</el-checkbox>
          </div>
        </el-checkbox-group>
        <div v-if="!filteredSecondaryColumns.length" class="column-settings__empty">{{ searchKeyword.trim() ? '没有匹配的字段，请调整关键词' : '暂无可选字段' }}</div>
      </template>
      <div class="column-settings__footer">
        <span>拖动 ⠿ 调整顺序，勾选与排序即时生效并自动保存</span>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { matchesSearch } from '@/utils/searchMatching'
import ColumnDefaultActions from './ColumnDefaultActions.vue'
import { useTableColumnOrder } from '@/composables/useTableColumnOrder'
import { moveColumn } from '@/utils/tableColumnOrder'
import { bindColumnDrag } from '@/utils/columnDragGesture'

const props = defineProps({
  settingsKey: { type: String, required: true },
  modelValue: { type: Array, required: true },
  columns: { type: Array, required: true },
  columnCount: { type: Number, default: 1 },
  hint: { type: String, default: '' },
  title: { type: String, default: '主表字段' },
  secondaryModelValue: { type: Array, default: () => [] },
  secondaryColumns: { type: Array, default: () => [] },
  secondaryColumnCount: { type: Number, default: 2 },
  secondaryTitle: { type: String, default: '子表字段' },
  secondaryHint: { type: String, default: '' }
})

const searchKeyword = ref('')
const mainOrder = useTableColumnOrder(computed(() => props.settingsKey), 'main', computed(() => props.columns))
const secondaryOrder = useTableColumnOrder(computed(() => props.settingsKey), 'secondary', computed(() => props.secondaryColumns))
const filteredColumns = computed(() => mainOrder.orderedColumns.value.filter(column => matchesSearch(column.label, searchKeyword.value)))
const filteredSecondaryColumns = computed(() => secondaryOrder.orderedColumns.value.filter(column => matchesSearch(column.label, searchKeyword.value)))
const emit = defineEmits(['update:modelValue', 'update:secondaryModelValue', 'reset', 'resetSecondary'])
const dropKey = ref(null), dragSecondary = ref(false)
const settingsRoot = ref(null)
let unbindDrag
watch(settingsRoot, root => {
  unbindDrag?.()
  if (!root) return
  unbindDrag = bindColumnDrag(root, (element, moving = true) => {
    if (!moving && !element?.closest('.column-settings__drag')) return null
    const handle = element?.closest('.column-settings__item')?.querySelector('.column-settings__drag')
    return handle && root.contains(handle) ? { key: handle.dataset.columnKey, secondary: handle.dataset.secondary === 'true' } : null
  }, (from, to) => {
    if (from.secondary !== to.secondary) return
    const state = from.secondary ? secondaryOrder : mainOrder
    const keys = state.order.value
    state.setOrder(moveColumn(keys, keys.find(key => String(key) === from.key), keys.find(key => String(key) === to.key)))
  }, target => { dropKey.value = target?.key ?? null; dragSecondary.value = target?.secondary ?? false })
}, { flush: 'post' })
onBeforeUnmount(() => unbindDrag?.())
function moveByKeyboard(key, direction, secondary) {
  const state = secondary ? secondaryOrder : mainOrder
  const visible = secondary ? filteredSecondaryColumns.value : filteredColumns.value
  const target = visible[visible.findIndex(column => column.key === key) + direction]
  if (target) state.setOrder(moveColumn(state.order.value, key, target.key))
}
function reset(secondary) {
  ;(secondary ? secondaryOrder : mainOrder).resetOrder()
  emit(secondary ? 'resetSecondary' : 'reset')
}
</script>

<style scoped>
.column-settings { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.column-settings__search { position: sticky; top: 0; z-index: 1; padding: 0 0 12px; background: var(--el-bg-color-overlay); }
.column-settings__matches { margin-bottom: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.column-settings__empty { padding: 18px 8px; color: var(--el-text-color-secondary); font-size: 13px; text-align: center; }
.column-settings__section-header { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 10px 16px; padding-bottom: 10px; }
.column-settings__section-title { color: var(--el-text-color-primary); font-weight: 600; }
.column-settings__summary { display: flex; gap: 16px; margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; }
.column-settings__hint { margin: 0 0 10px; padding: 8px 10px; border-radius: 4px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); font-size: 12px; line-height: 1.5; }
.column-settings :deep(.el-checkbox-group) { display: grid; column-gap: 24px; row-gap: 2px; align-items: start; }
.column-settings :deep(.el-checkbox) { width: 100%; margin-right: 0; }
.column-settings__item { display: flex; align-items: center; min-width: 0; border-radius: 4px; }
.column-settings__item.is-drop-target { background: var(--el-color-primary-light-9); box-shadow: inset 0 2px var(--el-color-primary); }
.column-settings__drag { touch-action: none; border: 0; background: transparent; padding: 4px 6px; color: var(--el-text-color-secondary); font-size: 20px; cursor: grab; flex-shrink: 0; }
.column-settings__drag:active { cursor: grabbing; }
.column-settings__drag:focus-visible { outline: 2px solid var(--el-color-primary); }
.column-settings__item :deep(.el-checkbox) { min-width: 0; }
.column-settings__item :deep(.el-checkbox__label) { overflow: hidden; text-overflow: ellipsis; }
.column-settings__footer { position: sticky; bottom: 0; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); color: var(--el-text-color-secondary); background: var(--el-bg-color-overlay); font-size: 12px; text-align: right; }
:global(.table-column-settings-popover) { max-width: calc(100vw - 32px) !important; }
</style>
