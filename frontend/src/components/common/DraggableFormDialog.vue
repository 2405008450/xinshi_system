<template>
  <el-dialog
    ref="dialogRef"
    v-bind="$attrs"
    :model-value="modelValue"
    class="draggable-form-dialog"
    draggable
    :overflow="false"
    @update:model-value="handleModelValueUpdate"
    @open="handleOpen"
  >
    <template v-for="(_, slotName) in $slots" #[slotName]="slotProps">
      <slot :name="slotName" v-bind="slotProps" />
    </template>
  </el-dialog>
</template>

<script setup>
import { nextTick, ref } from 'vue'

defineOptions({
  name: 'DraggableFormDialog',
  inheritAttrs: false,
})

defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'open'])
const dialogRef = ref(null)

const resetPosition = () => nextTick(() => dialogRef.value?.resetPosition?.())

const handleModelValueUpdate = (value) => {
  emit('update:modelValue', value)
}

const handleOpen = async () => {
  await resetPosition()
  emit('open')
}

defineExpose({ resetPosition })
</script>

<style>
.el-dialog.draggable-form-dialog {
  max-width: calc(100vw - 32px);
  transition: box-shadow 160ms ease;
}

.el-dialog.draggable-form-dialog.is-draggable .el-dialog__header {
  cursor: grab;
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
