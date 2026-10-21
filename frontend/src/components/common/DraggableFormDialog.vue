<template>
  <el-dialog
    ref="dialogRef"
    v-bind="maximizable ? { ...$attrs, fullscreen: maximized } : $attrs"
    :model-value="modelValue"
    class="draggable-form-dialog"
    :class="{ 'is-maximized': maximizable && maximized }"
    :draggable="draggable"
    :overflow="false"
    @update:model-value="handleModelValueUpdate"
    @open="handleOpen"
    @focusout.capture="handleFocusOut"
    @keydown.capture="handleKeydown"
  >
    <template v-for="slotName in forwardedSlotNames()" #[slotName]="slotProps">
      <slot :name="slotName" v-bind="slotProps" />
    </template>
    <template v-if="maximizable" #header="slotProps">
      <div class="draggable-form-dialog__heading">
        <div class="draggable-form-dialog__heading-content">
          <slot name="header" v-bind="slotProps"><span class="el-dialog__title">{{ $attrs.title }}</span></slot>
        </div>
        <el-button link class="draggable-form-dialog__maximize" :aria-label="maximized ? '还原窗口' : '最大化窗口'"
          :title="maximized ? '还原窗口' : '最大化窗口'" :aria-pressed="maximized" @mousedown.stop @dblclick.stop @click="toggleMaximized">
          <span class="dialog-maximize-icon" :class="{ 'dialog-maximize-icon--restore': maximized }" aria-hidden="true" />
          {{ maximized ? '还原' : '最大化' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { nextTick, onMounted, ref, useSlots } from 'vue'

defineOptions({
  name: 'DraggableFormDialog',
  inheritAttrs: false,
})

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  draggable: { type: Boolean, default: true },
  nonModal: { type: Boolean, default: false },
  resetOnOpen: { type: Boolean, default: true },
  maximizable: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'open'])
const dialogRef = ref(null)
const maximized = ref(false)
const slots = useSlots()
const forwardedSlotNames = () => Object.keys(slots).filter(name => !props.maximizable || name !== 'header')

const resetPosition = () => nextTick(() => dialogRef.value?.resetPosition?.())
const handleClose = () => dialogRef.value?.handleClose?.()

async function toggleMaximized() {
  // 使用 Dialog 原生布局切换，保留正文节点、Office iframe 和未保存内容。
  maximized.value = !maximized.value
  await nextTick()
  if (!maximized.value) await resetPosition()
}

// 无模态小窗允许焦点离开；普通业务弹窗继续使用 Element Plus 的焦点锁定。
const handleFocusOut = (event) => {
  // 固定聊天小窗是表单旁的协作入口，允许焦点在它和当前表单之间切换。
  if (props.nonModal || event.relatedTarget?.closest?.('.project-chat-window--pinned')) event.stopImmediatePropagation()
}
const handleKeydown = (event) => {
  if (props.nonModal && ['Tab', 'Escape'].includes(event.key)) event.stopImmediatePropagation()
}

const handleModelValueUpdate = (value) => {
  emit('update:modelValue', value)
}

const handleOpen = async () => {
  if (props.maximizable) maximized.value = false
  if (props.resetOnOpen) await resetPosition()
  else await nextTick()
  if (props.nonModal) {
    const content = dialogRef.value?.dialogContentRef?.$el
    content?.closest('[role="dialog"]')?.setAttribute('aria-modal', 'false')
  }
  emit('open')
  // 通知已固定的全局小窗调整层级；不干预下拉面板和确认框。
  document.dispatchEvent(new CustomEvent('app-dialog-opened', {
    detail: { element: dialogRef.value?.dialogContentRef?.$el },
  }))
}

// 按需挂载的全局小窗初始即打开，Element Plus 此时不会触发 open 事件。
onMounted(() => {
  if (props.modelValue) handleOpen()
})

defineExpose({ resetPosition, handleClose })
</script>

<style>
.el-dialog.draggable-form-dialog {
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 32px);
  max-height: 90vh;
  overflow: hidden;
  transition: box-shadow 160ms ease;
}

.el-dialog.draggable-form-dialog > .el-dialog__header {
  flex-shrink: 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.el-dialog.draggable-form-dialog > .el-dialog__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.el-dialog.draggable-form-dialog > .el-dialog__footer {
  flex-shrink: 0;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}

.el-dialog.draggable-form-dialog.is-maximized {
  width: calc(100vw - 32px);
  max-width: calc(100vw - 32px);
  height: calc(100dvh - 32px);
  max-height: calc(100dvh - 32px);
  margin: 16px auto;
}

.draggable-form-dialog__heading { display: flex; align-items: center; gap: 12px; min-width: 0; }
.draggable-form-dialog__heading-content { flex: 1; min-width: 0; }
.draggable-form-dialog__maximize { flex-shrink: 0; margin-right: 28px; gap: 6px; }
.dialog-maximize-icon { position: relative; display: inline-block; width: 13px; height: 11px; border: 1px solid currentColor; box-sizing: border-box; margin-right: 6px; }
.dialog-maximize-icon--restore { width: 10px; height: 9px; margin-top: 3px; margin-right: 9px; }
.dialog-maximize-icon--restore::before { content: ''; position: absolute; width: 10px; height: 9px; box-sizing: border-box; border-top: 1px solid currentColor; border-right: 1px solid currentColor; top: -4px; left: 2px; }

.el-dialog.draggable-form-dialog.is-draggable .el-dialog__header {
  cursor: grab;
  user-select: none;
}

.el-dialog.draggable-form-dialog.is-dragging {
  box-shadow: 0 18px 48px rgb(15 23 42 / 24%);
}

.el-dialog.draggable-form-dialog.is-dragging .el-dialog__header {
  cursor: grabbing;
}

.el-dialog.draggable-form-dialog .el-dialog__headerbtn,
.el-dialog.draggable-form-dialog .el-dialog__header button,
.el-dialog.draggable-form-dialog .el-dialog__header a {
  cursor: pointer;
}

.el-dialog.draggable-form-dialog .el-dialog__header input,
.el-dialog.draggable-form-dialog .el-dialog__header textarea {
  cursor: text;
  user-select: text;
}

@media (pointer: coarse) {
  .el-dialog.draggable-form-dialog.is-draggable .el-dialog__header {
    cursor: default;
  }
}
</style>
