<template>
  <div v-if="enabled" ref="layoutRef" class="project-arrangement-layout" :class="{'is-resizing':resizing}" :style="layoutStyle">
    <slot name="personnel"><ArrangementPersonnel :model-value="modelValue" :disabled="!canWrite" @update:model-value="$emit('update:modelValue',$event)" /></slot>
    <div class="arrangement-splitter" role="separator" tabindex="0" aria-label="调整人员区与项目区宽度" aria-orientation="vertical" :aria-valuenow="Math.round(effectiveRatio*100)" :aria-valuemin="Math.round(bounds.min*100)" :aria-valuemax="Math.round(bounds.max*100)" title="拖动调整左右宽度，双击恢复默认" @pointerdown="startResize" @keydown="resizeByKeyboard" @dblclick="resetRatio"><span /></div>
    <div class="project-arrangement-main"><slot /></div>
  </div>
  <slot v-else />
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import ArrangementPersonnel from '@/components/common/ArrangementPersonnel.vue'
defineProps({enabled:Boolean,canWrite:Boolean,modelValue:{type:Array,default:()=>[]}})
defineEmits(['update:modelValue'])
const DEFAULT_RATIO=1/6
const layoutRef=ref(null),width=ref(0),ratio=ref(DEFAULT_RATIO),resizing=ref(false)
let observer,stopDrag
const storageKey=()=>{try{return `translation-project-arrangement:split-v2:${localStorage.getItem('user_id')||'anonymous'}`}catch{return ''}}
try{
  const key=storageKey(),raw=localStorage.getItem(key)
  if(raw!==null){const value=JSON.parse(raw);if(typeof value==='number'&&Number.isFinite(value)&&value>=0.10&&value<=0.65)ratio.value=value;else localStorage.removeItem(key)}
  else{
    const previous=localStorage.getItem(key.replace(':split-v2:',':split:')),value=previous===null?null:JSON.parse(previous)
    if(typeof value==='number'&&Number.isFinite(value)&&value>=0.15&&value<=0.65)ratio.value=value*2/3
    localStorage.setItem(key,JSON.stringify(ratio.value))
  }
}catch{/* 使用默认比例。 */}
const availableWidth=computed(()=>Math.max(1,width.value-28))
const bounds=computed(()=>{const min=Math.min(0.65,Math.max(0.10,180/availableWidth.value));return {min,max:Math.max(min,Math.min(0.65,1-360/availableWidth.value))}})
const clamp=value=>Math.min(bounds.value.max,Math.max(bounds.value.min,value))
const effectiveRatio=computed(()=>clamp(ratio.value))
const layoutStyle=computed(()=>width.value?{'--arrangement-left-width':`${availableWidth.value*effectiveRatio.value}px`}:{})
function persist(){try{localStorage.setItem(storageKey(),JSON.stringify(ratio.value))}catch{/* 本地存储不可用时仍可调整。 */}}
function resetRatio(){ratio.value=DEFAULT_RATIO;persist()}
function startResize(event){
  if(event.button!==0||window.matchMedia('(max-width:960px)').matches)return
  event.preventDefault();stopDrag?.()
  const startX=event.clientX,startRatio=effectiveRatio.value,total=availableWidth.value,pointerId=event.pointerId
  const previousSelect=document.body.style.userSelect,previousCursor=document.body.style.cursor
  document.body.style.userSelect='none';document.body.style.cursor='col-resize';resizing.value=true
  const move=e=>{if(e.pointerId===pointerId)ratio.value=clamp(startRatio+(e.clientX-startX)/total)}
  stopDrag=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',finish);window.removeEventListener('blur',finish);document.body.style.userSelect=previousSelect;document.body.style.cursor=previousCursor;resizing.value=false;stopDrag=undefined}
  const finish=()=>{stopDrag?.();persist()}
  window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish,{once:true});window.addEventListener('pointercancel',finish,{once:true});window.addEventListener('blur',finish,{once:true})
}
function resizeByKeyboard(event){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return
  event.preventDefault()
  ratio.value=event.key==='Home'?bounds.value.min:event.key==='End'?bounds.value.max:clamp(effectiveRatio.value+(event.key==='ArrowLeft'?-0.02:0.02))
  persist()
}
watch(layoutRef,element=>{stopDrag?.();observer?.disconnect();if(!element)return;width.value=element.clientWidth;observer=new ResizeObserver(()=>{width.value=element.clientWidth});observer.observe(element)},{flush:'post'})
onBeforeUnmount(()=>{stopDrag?.();observer?.disconnect()})
</script>
<style scoped>
.project-arrangement-layout{display:grid;grid-template-columns:minmax(180px,var(--arrangement-left-width,16.6667%)) 12px minmax(0,1fr);gap:8px;align-items:start}.project-arrangement-main{min-width:0}.arrangement-splitter{align-self:stretch;min-height:240px;display:flex;align-items:center;justify-content:center;cursor:col-resize;touch-action:none;border-radius:6px;background:#f1f5f9;outline-offset:2px}.arrangement-splitter span{width:3px;height:42px;border-radius:3px;background:#94a3b8}.arrangement-splitter:hover,.arrangement-splitter:focus-visible,.is-resizing .arrangement-splitter{background:#dbeafe}.arrangement-splitter:focus-visible{outline:2px solid #409eff}.is-resizing{user-select:none}@media(max-width:960px){.project-arrangement-layout{grid-template-columns:1fr;gap:16px}.arrangement-splitter{display:none}.project-arrangement-layout :deep(.arrangement-personnel){max-height:300px}}
</style>
