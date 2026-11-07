<template>
  <ElPopover
    ref="popoverRef"
    v-bind="$attrs"
    :title="''"
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
        <WindowControls :maximized="geometry.state.maximized" @minimize="minimized = true" @maximize="geometry.maximize" @restore="geometry.restore" @close="close" />
      </header>
      <div ref="content" class="app-window-popover__body"><slot>{{ $attrs.content }}</slot></div>
      <i v-for="edge in geometry.state.maximized?[]:edges" :key="edge" class="app-window-resize" :class="`app-window-resize--${edge}`" @mousedown="geometry.start($event, edge)" />
    </template>
    <slot v-else>{{ $attrs.content }}</slot>
    <SelectionPopoverSummary ref="selectionSummary" :groups="selectionGroups" @confirm="confirmSelection" />
  </ElPopover>
  <WindowMinibar v-if="minimized" :title="title" @restore="minimized = false" @close="close" />
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

defineOptions({ inheritAttrs: false })
defineProps({ title: { type: String, default: '' } })
const emit = defineEmits(['update:visible'])
const attrs = useAttrs()
const selectionGroups = shallowReactive(new Map()), selectionSummary = ref()
provide(multiSelectionContext, selectionGroups)
function confirmSelection() {
  const panel = selectionSummary.value?.$el?.closest('.el-popover')
  const existing = [...(panel?.querySelectorAll('button') || [])].find(button =>
    !button.closest('.multi-select-summary') && button.getClientRects().length && /^(确定|确认|应用|保存|查询|完成|确认选择)$/.test(button.textContent.trim()))
  if (existing) { if (!existing.disabled) existing.click() }
  else close()
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
  maximize: geometry.maximize,
  resetPosition: geometry.reset,
})
</script>

<style>
.el-popover.app-window-popover { display: flex; flex-direction: column; max-width: calc(100vw - 16px); max-height: calc(100vh - 16px); box-sizing: border-box; }
.app-window-popover--maximized .el-popper__arrow{display:none}.app-window-popover--maximized .app-window-popover__header{cursor:default}
.app-window-popover__header { position: relative; flex-shrink: 0; min-height: 36px; padding: 4px 140px 8px 0; cursor: grab; border-bottom: 1px solid var(--el-border-color-lighter); }
.app-window-popover__title { font-size: 16px; color: var(--el-text-color-primary); overflow-wrap: anywhere; cursor: text; user-select: text; }
.app-window-popover__header.is-dragging { cursor: grabbing; }
.app-window-popover__body { flex: 1; min-height: 0; overflow: auto; }
.app-window-popover__body > * { max-height: none !important; }
</style>
