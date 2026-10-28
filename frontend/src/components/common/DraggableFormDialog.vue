<template>
  <el-dialog
    ref="dialogRef"
    v-bind="$attrs"
    :model-value="modelValue && !minimized"
    :class="['draggable-form-dialog', { 'is-draggable': draggable && !geometry.state.maximized, 'is-dragging': geometry.state.dragging, 'is-maximized': geometry.state.maximized }]"
    :draggable="false"
    :overflow="false"
    :show-close="false"
    :destroy-on-close="minimized ? false : ($attrs.destroyOnClose ?? $attrs['destroy-on-close'])"
    :style="geometryStyle"
    @update:model-value="handleModelValueUpdate"
    @open="handleOpen"
    @opened="handleOpened"
    @close="!minimized && emit('close')"
    @closed="handleClosed"
    @mousedown.capture="headerDrag"
    @focusout.capture="handleFocusOut"
    @keydown.capture="handleKeydown"
  >
    <template #header="slotProps">
      <slot name="header" v-bind="slotProps"><span :id="slotProps.titleId" class="el-dialog__title">{{ $attrs.title }}</span></slot>
      <WindowControls :maximized="geometry.state.maximized" @minimize="minimize" @maximize="geometry.maximize" @restore="geometry.restore" @close="handleClose" />
    </template>
    <template v-for="slotName in Object.keys($slots).filter(name=>!['header','default'].includes(name))" #[slotName]="slotProps">
      <slot :name="slotName" v-bind="slotProps" />
    </template>
    <template #default><slot /><Teleport v-if="contentElement && !geometry.state.maximized" :to="contentElement"><i v-for="edge in ['n','s','w','e','nw','ne','sw','se']" :key="edge" class="app-window-resize" :class="`app-window-resize--${edge}`" :title="'拖动调整窗口大小'" @mousedown="geometry.start($event,edge)" /></Teleport></template>
  </el-dialog>
  <WindowMinibar v-if="modelValue && minimized" :title="minimizedTitle" @restore="restoreMinimized" @close="closeMinimized" />
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useAttrs, watch } from 'vue'
import WindowControls from './WindowControls.vue'
import WindowMinibar from './WindowMinibar.vue'
import { useWindowGeometry } from '@/composables/useWindowGeometry'

defineOptions({
  name: 'DraggableFormDialog',
  inheritAttrs: false,
})

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  draggable: { type: Boolean, default: true },
  nonModal: { type: Boolean, default: false },
  resetOnOpen: { type: Boolean, default: true },
  defaultMaximized: { type: Boolean, default: false },
  maximizeTarget: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'open','opened','close','closed'])
const dialogRef = ref(null)
const contentElement=ref(null)
const attrs=useAttrs(),minimized=ref(false),restoring=ref(false),minimizedTitle=ref('窗口')
function maximizeBounds(){
  const target=props.maximizeTarget&&document.querySelector(props.maximizeTarget)
  if(!target)return null
  const bounds=target.getBoundingClientRect()
  let left=Math.max(0,bounds.left),top=Math.max(0,bounds.top),right=Math.min(window.innerWidth,bounds.right),bottom=window.innerHeight
  // 内容可能比一屏更长；仅覆盖当前可见区域，保留导航与侧栏。
  for(let parent=target.parentElement;parent&&parent!==document.body;parent=parent.parentElement){
    const style=getComputedStyle(parent),rect=parent.getBoundingClientRect()
    if(/auto|scroll|hidden|clip/.test(style.overflowY)){top=Math.max(top,rect.top);bottom=Math.min(bottom,rect.bottom)}
    if(/auto|scroll|hidden|clip/.test(style.overflowX)){left=Math.max(left,rect.left);right=Math.min(right,rect.right)}
  }
  return {x:left,y:top,width:Math.max(1,right-left),height:Math.max(1,bottom-top)}
}
const geometry=useWindowGeometry(()=>dialogRef.value?.dialogContentRef?.$el||dialogRef.value?.$el?.querySelector?.('.el-dialog'),{maximizeBounds})
let targetObserver
const refreshTargetBounds=()=>{if(geometry.state.maximized&&props.maximizeTarget)geometry.refreshBounds()}
function observeTarget(){
  targetObserver?.disconnect()
  if(!props.maximizeTarget)return
  const target=document.querySelector(props.maximizeTarget)
  if(!target)return
  targetObserver=new ResizeObserver(refreshTargetBounds)
  targetObserver.observe(target)
  if(target.parentElement)targetObserver.observe(target.parentElement)
}
const geometryStyle=computed(()=>geometry.state.rect?{position:'fixed',left:`${geometry.state.rect.x}px`,top:`${geometry.state.rect.y}px`,width:`${geometry.state.rect.width}px`,height:`${geometry.state.rect.height}px`,margin:0,transform:'none',boxSizing:'border-box',maxWidth:geometry.state.maximized?'100vw':'calc(100vw - 16px)',maxHeight:geometry.state.maximized?'100vh':'calc(100vh - 16px)'}:{})
function headerDrag(event){
  if(!props.draggable||geometry.state.maximized||!event.target.closest('.el-dialog__header')||event.target.closest('button,a,input,textarea,select,[contenteditable],.is-copyable-title,.dialog-field-search-header__search'))return
  if(event.target.closest('.app-window-drag-strip'))return
  if(getComputedStyle(event.target).userSelect==='text')return
  geometry.start(event)
}
function minimize(){const el=dialogRef.value?.dialogContentRef?.$el;minimizedTitle.value=attrs.title||el?.querySelector('.el-dialog__header')?.innerText?.split('\n')[0]||'窗口';minimized.value=true}
function restoreMinimized(){restoring.value=true;minimized.value=false}
function closeMinimized(){const done=()=>{minimized.value=false;emit('update:modelValue',false);emit('close');emit('closed')};const before=attrs.beforeClose??attrs['before-close'];if(before)before(done);else done()}
function handleOpened(){contentElement.value=dialogRef.value?.dialogContentRef?.$el;if(restoring.value){restoring.value=false;return}emit('opened')}
function handleClosed(){if(!minimized.value)emit('closed')}
watch(()=>props.modelValue,value=>{if(!value){minimized.value=false;restoring.value=false;geometry.reset();contentElement.value=null}})
onBeforeUnmount(()=>{minimized.value=false;targetObserver?.disconnect();window.removeEventListener('scroll',refreshTargetBounds,true)})

const resetPosition = () => {geometry.reset();return nextTick(() => dialogRef.value?.resetPosition?.())}
const handleClose = () => dialogRef.value?.handleClose?.()

// 无模态小窗允许焦点离开；普通业务弹窗继续使用 Element Plus 的焦点锁定。
const handleFocusOut = (event) => {
  // 固定聊天小窗是表单旁的协作入口，允许焦点在它和当前表单之间切换。
  if (props.nonModal || event.relatedTarget?.closest?.('.project-chat-window--pinned')) event.stopImmediatePropagation()
}
const handleKeydown = (event) => {
  if (props.nonModal && ['Tab', 'Escape'].includes(event.key)) event.stopImmediatePropagation()
}

const handleModelValueUpdate = (value) => {
  if(minimized.value)return
  emit('update:modelValue', value)
}

const handleOpen = async () => {
  if(restoring.value)return
  if (props.resetOnOpen) await resetPosition()
  else await nextTick()
  if (props.defaultMaximized) geometry.maximize()
  observeTarget()
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
  window.addEventListener('scroll',refreshTargetBounds,true)
  if (props.modelValue) handleOpen()
})

defineExpose({ resetPosition, handleClose, minimize, restore:restoreMinimized, maximize:geometry.maximize })
</script>

<style>
.app-window-controls{position:absolute;top:4px;right:4px;display:flex;z-index:5;gap:2px}.app-window-controls button{width:30px;height:28px;border:0;border-radius:4px;background:transparent;color:#475569;font-size:19px;cursor:pointer}.app-window-controls button:hover{background:#e2e8f0}.app-window-controls button:last-child:hover{background:#fee2e2;color:#dc2626}.app-window-controls button:disabled{opacity:.4;cursor:default}.app-window-drag-strip{position:absolute;left:0;right:140px;top:0;height:24px;cursor:grab;z-index:3}.app-window-resize{position:absolute;z-index:8;display:block}.app-window-resize--n,.app-window-resize--s{height:6px;left:8px;right:8px;cursor:ns-resize}.app-window-resize--n{top:0}.app-window-resize--s{bottom:0}.app-window-resize--w,.app-window-resize--e{width:6px;top:8px;bottom:8px;cursor:ew-resize}.app-window-resize--w{left:0}.app-window-resize--e{right:0}.app-window-resize--nw,.app-window-resize--ne,.app-window-resize--sw,.app-window-resize--se{width:12px;height:12px}.app-window-resize--nw{left:0;top:0;cursor:nwse-resize}.app-window-resize--ne{right:0;top:0;cursor:nesw-resize}.app-window-resize--sw{left:0;bottom:0;cursor:nesw-resize}.app-window-resize--se{right:0;bottom:0;cursor:nwse-resize;background:linear-gradient(135deg,transparent 50%,#94a3b8 50%,#94a3b8 58%,transparent 58%,transparent 70%,#94a3b8 70%,#94a3b8 78%,transparent 78%)}.app-window-minibar{position:fixed;bottom:12px;z-index:200000;display:flex;max-width:210px;padding:5px;background:#fff;box-shadow:0 3px 16px #0f172a30;border:1px solid #cbd5e1;border-radius:8px}.app-window-minibar button{border:0;background:none;cursor:pointer;color:#334155;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:7px}.app-window-minibar button:first-child{max-width:175px}
.el-dialog.draggable-form-dialog {
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 32px);
  max-height: 90vh;
  overflow: hidden;
  transition: box-shadow 160ms ease;
}

.el-dialog.draggable-form-dialog.is-maximized {
  border-radius: 0;
}
.el-dialog.draggable-form-dialog.is-maximized > .el-dialog__header {
  cursor: default;
}

.el-dialog.draggable-form-dialog > .el-dialog__header {
  position:relative;
  padding-top:8px;
  min-height:36px;
  padding-right:144px;
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
