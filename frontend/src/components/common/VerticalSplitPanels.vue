<template>
  <div ref="root" class="vertical-split-panels" :class="{'is-resizing':dragging}" :style="layoutStyle">
    <div v-show="!topClosed" class="vertical-split-top"><slot name="top" /></div>
    <div class="vertical-split-controls">
      <button type="button" :aria-expanded="!topClosed" :title="topClosed?'展开'+topLabel:'折叠'+topLabel" @click="toggleTop">{{ topClosed?'▾':'▴' }} {{ topLabel }}</button>
      <div class="vertical-split-handle" role="separator" tabindex="0" aria-orientation="horizontal" :aria-label="`调整${topLabel}与${bottomLabel}高度`" :aria-valuenow="Math.round(effectiveRatio*100)" :aria-valuemin="Math.round(bounds.min*100)" :aria-valuemax="Math.round(bounds.max*100)" :aria-disabled="topClosed||bottomClosed" title="上下拖动调整区域大小；双击恢复；上下方向键微调" @pointerdown="start" @keydown="keyboard" @dblclick="reset"><span>⋯</span></div>
      <button type="button" :aria-expanded="!bottomClosed" :title="bottomClosed?'展开'+bottomLabel:'折叠'+bottomLabel" @click="toggleBottom">{{ bottomClosed?'▴':'▾' }} {{ bottomLabel }}</button>
    </div>
    <div v-show="!bottomClosed" class="vertical-split-bottom"><slot name="bottom" /></div>
  </div>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
const props=defineProps({topLabel:{type:String,default:'上方区域'},bottomLabel:{type:String,default:'下方区域'},defaultRatio:{type:Number,default:.4},minTop:{type:Number,default:220},minBottom:{type:Number,default:120}})
const root=ref(null),height=ref(0),ratio=ref(props.defaultRatio),dragging=ref(false),topClosed=ref(false),bottomClosed=ref(false)
let observer,stopDrag
const usable=computed(()=>Math.max(1,height.value-32))
const bounds=computed(()=>{const min=Math.min(.45,props.minTop/usable.value);return {min,max:Math.max(min,Math.min(.9,1-props.minBottom/usable.value))}})
const clamp=value=>Math.min(bounds.value.max,Math.max(bounds.value.min,value))
const effectiveRatio=computed(()=>clamp(ratio.value))
const layoutStyle=computed(()=>({gridTemplateRows:topClosed.value?'0px 32px minmax(0,1fr)':bottomClosed.value?'minmax(0,1fr) 32px 0px':`${Math.round(usable.value*effectiveRatio.value)}px 32px minmax(0,1fr)`}))
function reset(){stopDrag?.();ratio.value=props.defaultRatio;topClosed.value=false;bottomClosed.value=false}
function toggleTop(){stopDrag?.();topClosed.value=!topClosed.value;if(topClosed.value)bottomClosed.value=false}
function toggleBottom(){stopDrag?.();bottomClosed.value=!bottomClosed.value;if(bottomClosed.value)topClosed.value=false}
function keyboard(event){
 if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key)||topClosed.value||bottomClosed.value)return
 event.preventDefault()
 ratio.value=event.key==='Home'?bounds.value.min:event.key==='End'?bounds.value.max:clamp(effectiveRatio.value+(event.key==='ArrowUp'?-.02:.02))
}
function start(event){
 if(event.button!==0||topClosed.value||bottomClosed.value)return
 event.preventDefault();stopDrag?.()
 const begin=event.clientY,initial=effectiveRatio.value,total=usable.value,pointer=event.pointerId
 const select=document.body.style.userSelect,cursor=document.body.style.cursor
 document.body.style.userSelect='none';document.body.style.cursor='row-resize';dragging.value=true
 const move=event=>{if(event.pointerId===pointer)ratio.value=clamp(initial+(event.clientY-begin)/total)}
 const finish=()=>stopDrag?.()
 stopDrag=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',finish);window.removeEventListener('blur',finish);document.body.style.userSelect=select;document.body.style.cursor=cursor;dragging.value=false;stopDrag=undefined}
 window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);window.addEventListener('blur',finish)
}
watch(root,element=>{observer?.disconnect();if(!element)return;height.value=element.clientHeight;observer=new ResizeObserver(()=>height.value=element.clientHeight);observer.observe(element)},{flush:'post'})
onBeforeUnmount(()=>{stopDrag?.();observer?.disconnect()})
</script>
<style scoped>
.vertical-split-top{grid-row:1}.vertical-split-controls{grid-row:2}.vertical-split-bottom{grid-row:3}
.vertical-split-panels{flex:1;min-height:0;min-width:0;display:grid;overflow:hidden}.vertical-split-top,.vertical-split-bottom{min-height:0;min-width:0;overflow:hidden}.vertical-split-controls{min-height:0;display:flex;align-items:stretch;border-top:1px solid #cbd5e1;border-bottom:1px solid #cbd5e1;background:#f1f5f9;box-sizing:border-box}.vertical-split-controls button{flex:none;border:0;background:transparent;padding:0 12px;font:inherit;font-size:12px;color:#475569;cursor:pointer;white-space:nowrap}.vertical-split-controls button:hover,.vertical-split-controls button:focus-visible{background:#dbeafe}.vertical-split-handle{flex:1;min-width:40px;display:flex;align-items:center;justify-content:center;cursor:row-resize;touch-action:none;color:#64748b;outline-offset:-2px}.vertical-split-handle span{font-size:22px;line-height:1}.vertical-split-handle:hover,.vertical-split-handle:focus-visible,.is-resizing .vertical-split-handle{background:#dbeafe}.vertical-split-handle:focus-visible{outline:2px solid #3b82f6}.vertical-split-handle[aria-disabled=true]{cursor:default}
</style>
