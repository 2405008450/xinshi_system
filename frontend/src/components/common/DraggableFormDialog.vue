<template>
  <el-dialog
    ref="dialogRef"
    v-bind="$attrs"
    :model-value="modelValue"
    class="draggable-form-dialog"
    :draggable="draggable"
    :overflow="false"
    @update:model-value="handleModelValueUpdate"
    @open="handleOpen"
    @focusout.capture="handleFocusOut"
    @keydown.capture="handleKeydown"
  >
    <template v-for="(_, slotName) in $slots" #[slotName]="slotProps">
      <slot :name="slotName" v-bind="slotProps" />
    </template>
  </el-dialog>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'

defineOptions({
  name: 'DraggableFormDialog',
  inheritAttrs: false,
})

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  draggable: { type: Boolean, default: true },
  nonModal: { type: Boolean, default: false },
  resetOnOpen: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'open'])
const dialogRef = ref(null)

const resetPosition = () => nextTick(() => dialogRef.value?.resetPosition?.())
const handleClose = () => dialogRef.value?.handleClose?.()

// 无模态小窗允许焦点离开；普通业务弹窗继续使用 Element Plus 的焦点锁定。
const handleFocusOut = (event) => {
  if (props.nonModal) event.stopImmediatePropagation()
}
const handleKeydown = (event) => {
  if (props.nonModal && ['Tab', 'Escape'].includes(event.key)) event.stopImmediatePropagation()
}

const handleModelValueUpdate = (value) => {
  emit('update:modelValue', value)
}

const handleOpen = async () => {
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
  max-width: calc(100vw - 32px);
  transition: box-shadow 160ms ease;
}

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
