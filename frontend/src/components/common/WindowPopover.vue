<template>
  <ElPopover
    ref="popoverRef"
    v-bind="$attrs"
    :title="''"
    :trigger="attrs.trigger ?? (isFilter ? 'click' : undefined)"
    :visible="minimized ? true : visible"
    :popper-class="normalizeClass([$attrs.popperClass || $attrs['popper-class'], title && 'app-window-popover', geometry.state.maximized && 'app-window-popover--maximized'])"
    :popper-style="[$attrs.popperStyle || $attrs['popper-style'], windowStyle]"
    :on-update:visible="minimized ? undefined : updateVisible"
    @after-leave="reset"
  >
    <template v-if="$slots.reference" #reference><slot name="reference" /></template>
    <template v-if="title">
      <header class="app-window-popover__header" :class="{ 'is-dragging': geometry.state.dragging }" @mousedown="drag" @dblclick.self="geometry.maximize">
        <span class="app-window-popover__title" @mousedown.stop>{{ title }}</span>
        <WindowControls :maximized="geometry.state.maximized" @minimize="minimized = true" @maximize="geometry.maximize" @restore="geometry.restore" @close="closeWindow" />
      </header>
      <div ref="content" class="app-window-popover__body">
        <FilterDraftScope v-if="isFilter" ref="draftScope">
          <slot>{{ $attrs.content }}</slot>
        </FilterDraftScope>
        <slot v-else>{{ $attrs.content }}</slot>
      </div>
      <div v-if="isFilter" class="filter-window-actions">
        <el-button link @click="cancelFilter">取消筛选</el-button>
        <el-button type="primary" @click="applyFilter">确定</el-button>
      </div>
      <i v-for="edge in geometry.state.maximized?[]:edges" :key="edge" class="app-window-resize" :class="`app-window-resize--${edge}`" @mousedown="geometry.start($event, edge)" />
    </template>
    <slot v-else>{{ $attrs.content }}</slot>
    <SelectionPopoverSummary v-if="!hideSelectionSummary" ref="selectionSummary" :groups="selectionGroups" @confirm="confirmSelection" />
  </ElPopover>
  <WindowMinibar v-if="minimized" :title="title" @restore="minimized = false" @close="closeWindow" />
</template>

<script setup>
import { computed, normalizeClass, provide, ref, shallowReactive, useAttrs, watch } from 'vue'
import { ElPopover } from 'element-plus'
import WindowControls from './WindowControls.vue'
import WindowMinibar from './WindowMinibar.vue'
import { useWindowGeometry } from '@/composables/useWindowGeometry'
import {isAdvancedFilterDockDragging} from '@/utils/advancedFilterDock'
import SelectionPopoverSummary from './selectionPopoverSummary.js'
import { multiSelectionContext } from './multiSelectionContext.js'
import FilterDraftScope from './FilterDraftScope'

defineOptions({ inheritAttrs: false })
const props = defineProps({ title: { type: String, default: '' }, retainOnSelection: Boolean,
  hideSelectionSummary: Boolean,
  draftFilter: { type: Boolean, default: undefined } })
const isFilter = computed(() => props.draftFilter ?? /筛选|排除项目状态|负责人变更|联系状态记录/.test(props.title))
const draftScope = ref()
function applyFilter(){draftScope.value?.apply();close()}
function cancelFilter(){draftScope.value?.cancel();close()}
const emit = defineEmits(['update:visible', 'window-close'])
const attrs = useAttrs()
const selectionGroups = shallowReactive(new Map()), selectionSummary = ref()
provide(multiSelectionContext, selectionGroups)
function confirmSelection() {
  if (isFilter.value) { applyFilter(); return }
  const panel = selectionSummary.value?.$el?.closest('.el-popover')
  const existing = [...(panel?.querySelectorAll('button') || [])].find(button =>
    !button.closest('.multi-select-summary') && button.getClientRects().length && /^(确定|确认|应用|保存|查询|完成|确认选择)$/.test(button.textContent.trim()))
  if (existing) { if (!existing.disabled) existing.click() }
  else if (!props.retainOnSelection) close()
}
const popoverRef = ref(), content = ref(), minimized = ref(false), localVisible = ref(), locallyClosed = ref(false)
// 兼容只传 :visible 的调用方：关闭按钮也必须即时关闭，而非等待外层状态回写。
const visible = computed(() => locallyClosed.value ? false : (attrs.visible ?? localVisible.value))
const geometry = useWindowGeometry(() => content.value?.closest('.el-popper'))
const edges = ['n', 's', 'w', 'e', 'nw', 'ne', 'sw', 'se']
const windowStyle = computed(() => {
  if (minimized.value) return { visibility: 'hidden', pointerEvents: 'none' }
  const rect = geometry.state.rect
  return rect ? {
    position: 'fixed !important', left: `${rect.x}px !important`, top: `${rect.y}px !important`,
    width: `${rect.width}px !important`, height: `${rect.height}px !important`,
    maxWidth: geometry.state.maximized?'none !important':'calc(100vw - 16px) !important', maxHeight: geometry.state.maximized?'none !important':'calc(100vh - 16px) !important',
    transform: 'none !important', margin: '0 !important',
  } : {}
})
function updateVisible(value) {
  if (minimized.value) return
  // 鼠标拖到浮窗外后释放，不应被原生 click-outside 当成关闭操作。
  if (value === false && (geometry.state.dragging||isAdvancedFilterDockDragging())) return
  locallyClosed.value = !value
  localVisible.value = value
  emit('update:visible', value)
}
function close() {
  minimized.value = false
  updateVisible(false)
  popoverRef.value?.hide()
}
function closeWindow() {
  emit('window-close')
  close()
}
function reset() { minimized.value = false; geometry.reset() }
function drag(event) {
  if (!event.target.closest('button,a,input,textarea,select')) geometry.start(event)
}
watch(() => attrs.visible, value => {
  if (value === true) locallyClosed.value = false
  if (value === false) reset()
})
defineExpose({
  popperRef: computed(() => popoverRef.value?.popperRef),
  hide: close,
  minimize: () => { if (visible.value) minimized.value = true },
  maximize: geometry.maximize,
  resetPosition: geometry.reset,
})
</script>

<style>
.el-popover.app-window-popover {
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 16px);
  max-height: calc(100vh - 16px);
  padding: 0 !important;
  border: 1px solid var(--color-border, #e2e8f0) !important;
  border-radius: var(--radius-lg, 12px) !important;
  background: var(--color-surface, #ffffff);
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.14), 0 2px 6px rgba(15, 23, 42, 0.05) !important;
  box-sizing: border-box;
  overflow: hidden;
}
.app-window-popover--maximized .el-popper__arrow { display: none; }
.app-window-popover--maximized .app-window-popover__header { cursor: default; }
.app-window-popover__header {
  position: relative;
  display: flex;
  align-items: center;
  flex-shrink: 0;
  min-height: 40px;
  padding: 8px 104px 8px 14px;
  background: var(--color-page-bg, #f8fafc);
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  cursor: grab;
}
.app-window-popover__header .app-window-controls {
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
}
.app-window-popover__header .app-window-controls button {
  width: 26px;
  height: 26px;
  font-size: 16px;
  line-height: 1;
  border-radius: 6px;
}
.app-window-popover__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--color-text-primary, #111827);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: text;
  user-select: text;
}
.app-window-popover__title::before {
  content: '';
  flex: none;
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: var(--color-primary, #334155);
}
.app-window-popover__header.is-dragging { cursor: grabbing; }
.app-window-popover__body {
  flex: 1;
  min-height: 0;
  padding: 12px 14px;
  overflow: auto;
}
.app-window-popover__body > * { max-height: none !important; }
.filter-window-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 9px 14px;
  background: var(--color-page-bg, #f8fafc);
  border-top: 1px solid var(--color-border, #e2e8f0);
  flex: none;
}
.filter-window-actions .el-button {
  min-height: 30px;
  height: 30px;
  padding: 4px 12px;
}
</style>
