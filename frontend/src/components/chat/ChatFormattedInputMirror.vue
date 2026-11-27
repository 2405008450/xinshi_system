<template>
 <Teleport v-if="enabled && field?.parentElement" :to="field.parentElement">
  <div class="chat-formatted-input-mirror" aria-hidden="true" :style="mirrorStyle"><div :style="{transform:`translate(${-scrollLeft}px, ${-scrollTop}px)`}"><span v-for="(run,index) in runs" :key="index" :style="runStyle(run.marks)">{{run.text}}</span></div></div>
 </Teleport>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {formatRuns,runStyle} from '@/utils/chatTextFormat'
import {screenshotPattern,screenshotMarker} from '@/utils/screenshotReferences'
const props=defineProps({field:Object,document:Object,enabled:Boolean})
const mirrorStyle=ref({}),scrollTop=ref(0),scrollLeft=ref(0)
const runs=computed(()=>formatRuns(props.document).map(run=>({...run,text:run.text.replace(/(?:\n)?\[附件\]\(discussion-file:\/\/[0-9a-f-]{36}\)/gi,'').replace(new RegExp(screenshotPattern),screenshotMarker)})))
let cleanup=()=>{}
watch(()=>[props.field,props.enabled],([field,enabled])=>{
 cleanup();cleanup=()=>{}
 if(!field||!enabled)return
 const parent=field.parentElement,oldPosition=parent.style.position,style=getComputedStyle(field),color=style.color
 const restorePosition=getComputedStyle(parent).position==='static'
 if(restorePosition)parent.style.position='relative'
 const sync=()=>{scrollTop.value=field.scrollTop;scrollLeft.value=field.scrollLeft}
 const measure=()=>{const css=getComputedStyle(field);mirrorStyle.value={left:`${field.offsetLeft+field.clientLeft}px`,top:`${field.offsetTop+field.clientTop}px`,width:`${field.clientWidth}px`,height:`${field.clientHeight}px`,padding:css.padding,fontFamily:css.fontFamily,fontSize:css.fontSize,fontWeight:css.fontWeight,fontStyle:css.fontStyle,lineHeight:css.lineHeight,letterSpacing:css.letterSpacing,textAlign:css.textAlign,wordBreak:css.wordBreak,overflowWrap:css.overflowWrap,tabSize:css.tabSize,color};sync()}
 field.classList.add('chat-format-editing-input');field.addEventListener('scroll',sync)
 const observer=new ResizeObserver(measure);observer.observe(field);measure()
 cleanup=()=>{observer.disconnect();field.removeEventListener('scroll',sync);field.classList.remove('chat-format-editing-input');if(restorePosition)parent.style.position=oldPosition}
},{flush:'post',immediate:true})
onBeforeUnmount(()=>cleanup())
</script>
<style>
.chat-formatted-input-mirror{position:absolute;box-sizing:border-box;overflow:hidden;white-space:pre-wrap;pointer-events:none;z-index:1}
textarea.chat-format-editing-input{position:relative;z-index:2;color:transparent!important;-webkit-text-fill-color:transparent!important;background:transparent!important;caret-color:var(--el-text-color-primary,#334155)}
textarea.chat-format-editing-input::selection{background:rgba(147,197,253,.4);color:transparent}
</style>
