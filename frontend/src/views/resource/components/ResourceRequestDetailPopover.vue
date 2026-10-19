<template>
  <el-popover ref="parentPopover" :visible="modelValue" :virtual-triggering="Boolean(virtualRef)" :virtual-ref="virtualRef" :teleported="teleported" trigger="click" placement="left" :width="760" :fallback-placements="['bottom', 'top', 'right']" :popper-options="viewportOptions" :title="title" popper-class="resource-detail-popover" @show="$emit('show')" @hide="$emit('hide')">
    <template #reference><span v-if="!virtualRef" ref="referenceRef" class="resource-detail-reference"><slot name="reference" :toggle="() => $emit('update:modelValue', !modelValue)"><el-button link type="primary" class="request-no-link business-clickable-cell" :title="`${request.requestNo || '-'}（点击查看详情）`" @click.stop="$emit('update:modelValue', !modelValue)">{{ referenceLabel || request.requestNo || '-' }}</el-button></slot></span></template>
    <div ref="parentPanel">
      <div v-show="!mobile || !projectOpen"><slot :openProject="openProject" :hasProject="Boolean(target)" /></div>
      <AssociatedProjectDetailPanel v-if="mobile && projectOpen" :source-type="target.sourceType" :project-id="target.projectId" :state="state" :title="projectTitle" :back-label="backLabel" mobile @close="closeProject()" @retry="reload" @enter="enterProject" />
    </div>
  </el-popover>
  <el-popover v-if="!mobile" ref="childPopover" :visible="modelValue && projectOpen" virtual-triggering :virtual-ref="projectTrigger" :teleported="teleported" placement="left" :width="760" :fallback-placements="['right', 'bottom', 'top']" :popper-options="viewportOptions" popper-class="associated-project-popover" @after-leave="restoreProjectFocus">
    <div ref="childPanel"><AssociatedProjectDetailPanel v-if="projectOpen && target" :source-type="target.sourceType" :project-id="target.projectId" :state="state" :title="projectTitle" @close="closeProject()" @retry="reload" @enter="enterProject" /></div>
  </el-popover>
</template>
<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { associatedProject, associatedProjectTypes, createAssociatedProjectLoader } from '@/utils/associatedProjectDetail'
import { fetchAssociatedProject } from '@/api/associatedProjectDetail'
import { arrangementProjectRoute } from '@/utils/resourceArrangements'
const AssociatedProjectDetailPanel = defineAsyncComponent(() => import('@/components/project/AssociatedProjectDetailPanel.vue'))
const props = defineProps({ modelValue: Boolean, request: { type: Object, required: true }, referenceLabel: String, virtualRef: Object, teleported: { type: Boolean, default: true }, title: { type: String, default: '资源需求详情' }, backLabel: { type: String, default: '返回资源需求' } })
const emit = defineEmits(['update:modelValue', 'show', 'hide'])
const router = useRouter()
const referenceRef = ref(), parentPanel = ref(), childPanel = ref(), projectTrigger = ref()
const parentPopover = ref(), childPopover = ref()
const mobile = ref(window.innerWidth <= 768), projectOpen = ref(false)
const target = computed(() => associatedProject(props.request))
const projectTitle = computed(() => `${associatedProjectTypes[target.value?.sourceType] || ''}项目详情`)
const state = reactive({ loading: false, detail: null, error: '', extras: {} })
let restoreFocusPending = false
let suppressedClickTarget
const loader = createAssociatedProjectLoader(fetchAssociatedProject, value => Object.assign(state, value))
const viewportOptions = { modifiers: [{ name: 'preventOverflow', options: { rootBoundary: 'viewport', altAxis: true, tether: false, padding: 16 } }] }
// 异步详情会改变浮层尺寸，需要在内容变化后重新核对视口位置。
function updatePosition() {
  nextTick(() => {
    parentPopover.value?.popperRef?.popperInstanceRef?.update()
    childPopover.value?.popperRef?.popperInstanceRef?.update()
  })
}
const observer = new ResizeObserver(updatePosition)
watch([parentPanel, childPanel], panels => { observer.disconnect(); panels.filter(Boolean).forEach(panel => observer.observe(panel)); updatePosition() }, { flush: 'post' })
function reload() { if (target.value && projectOpen.value) return loader.load(target.value) }
function openProject(element) {
  if (!target.value) return
  restoreFocusPending = false
  projectTrigger.value = element; projectOpen.value = true
  reload()
}
function closeProject(restoreFocus = true) {
  loader.cancel(); projectOpen.value = false
  restoreFocusPending = restoreFocus
  Object.assign(state, { loading: false, detail: null, error: '', extras: {} })
  if (mobile.value) nextTick(restoreProjectFocus)
}
function restoreProjectFocus() {
  if (restoreFocusPending && props.modelValue && !projectOpen.value) {
    projectTrigger.value?.focus({ preventScroll: true })
    restoreFocusPending = false
  }
}
function closeAll() { closeProject(false); emit('update:modelValue', false) }
function pointerDown(event) {
  if (!props.modelValue) return
  if (referenceRef.value?.contains(event.target) || props.virtualRef?.contains(event.target)) return
  if (projectOpen.value && childPanel.value?.contains(event.target)) return
  if (parentPanel.value?.closest('.el-popover')?.contains(event.target)) {
    if (projectOpen.value && !mobile.value) {
      suppressedClickTarget = event.target
      closeProject(); event.preventDefault(); event.stopImmediatePropagation()
    }
    return
  }
  closeAll()
}
function clickCapture(event) {
  const target = suppressedClickTarget
  suppressedClickTarget = null
  if (target === event.target) { event.preventDefault(); event.stopImmediatePropagation() }
}
function keyDown(event) {
  if (!props.modelValue || event.key !== 'Escape') return
  event.preventDefault(); event.stopImmediatePropagation()
  if (projectOpen.value) closeProject()
  else { closeAll(); nextTick(() => (props.virtualRef || referenceRef.value?.querySelector('button'))?.focus({ preventScroll: true })) }
}
function resize() { mobile.value = window.innerWidth <= 768 }
async function enterProject() {
  if (!state.detail || !target.value) return
  const location = arrangementProjectRoute({ source_type: target.value.sourceType, project_id: target.value.projectId, parent_project_id: state.detail.parentProjectId })
  closeAll()
  await router.push(location)
}
watch(() => props.modelValue, value => { if (!value) closeProject(false) }, { flush: 'sync' })
watch(() => `${target.value?.sourceType}:${target.value?.projectId}`, () => closeProject(false))
onMounted(() => { document.addEventListener('pointerdown', pointerDown, true); document.addEventListener('click', clickCapture, true); document.addEventListener('keydown', keyDown, true); window.addEventListener('resize', resize) })
onBeforeUnmount(() => { observer.disconnect(); loader.cancel(); document.removeEventListener('pointerdown', pointerDown, true); document.removeEventListener('click', clickCapture, true); document.removeEventListener('keydown', keyDown, true); window.removeEventListener('resize', resize) })
</script>
<style>
.resource-detail-popover.el-popper { width: min(760px, calc(100vw - 32px)) !important; max-width: calc(100vw - 32px); }
.resource-detail-reference { display: inline-flex; align-items: center; gap: 8px; min-width: 0; max-width: 100%; }
</style>
