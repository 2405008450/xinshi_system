<template>
  <el-popover
    ref="popoverRef"
    trigger="click"
    placement="left"
    :width="760"
    :popper-options="popperOptions"
    title="项目资料"
    popper-class="annotation-material-popover"
    @before-enter="handleOpen"
    @before-leave="handleClose"
  >
    <template #reference><el-button link type="primary">项目资料</el-button></template>
    <div ref="contentRef" class="annotation-material-popover__content">
      <AnnotationMaterialManager v-if="opened" :project-id="projectId" readonly />
    </div>
  </el-popover>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onDeactivated, ref } from 'vue'
import AnnotationMaterialManager from './AnnotationMaterialManager.vue'

defineProps({ projectId: { type: String, required: true } })

const popoverRef = ref(null), contentRef = ref(null), opened = ref(false)
const popperOptions = {
  modifiers: [{
    name: 'preventOverflow',
    options: { rootBoundary: 'viewport', altAxis: true, tether: false, padding: 16 },
  }],
}
let observer = null, updateFrame = null, generation = 0

function scheduleUpdate() {
  if (!opened.value || updateFrame !== null) return
  updateFrame = requestAnimationFrame(() => {
    updateFrame = null
    // ElPopover 暴露的是 Popper 实例；只更新定位，不改变浮层层级。
    if (opened.value) void popoverRef.value?.popperRef?.popperInstanceRef?.update()
  })
}

async function handleOpen() {
  const current = ++generation
  opened.value = true
  await nextTick()
  if (!opened.value || current !== generation) return
  observer?.disconnect()
  // 插槽异步挂载和资料加载均可能改变高度，必须在尺寸变化后重新避让视口。
  observer = new ResizeObserver(scheduleUpdate)
  observer.observe(contentRef.value)
  const popperElement = popoverRef.value?.popperRef?.contentRef
  if (popperElement) observer.observe(popperElement)
  scheduleUpdate()
}

function handleClose() {
  generation += 1
  opened.value = false
  observer?.disconnect()
  observer = null
  if (updateFrame !== null) cancelAnimationFrame(updateFrame)
  updateFrame = null
}

onBeforeUnmount(handleClose)
onDeactivated(handleClose)
</script>

<style>
.annotation-material-popover.el-popover {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 32px);
}
.annotation-material-popover > .el-popover__title { flex: none; }
.annotation-material-popover__content {
  flex: 1 1 auto;
  min-height: 0;
  max-height: min(560px, calc(100vh - 120px));
  overflow-y: auto;
  overflow-wrap: anywhere;
}
</style>
