<template>
 <el-popover title="文字格式" v-model:visible="visible" trigger="click" placement="top-start" :width="360" :z-index="popoverZ" popper-class="chat-text-format-popover">
  <template #reference><el-button class="chat-format-button" text size="small" aria-label="文字格式" title="文字格式" :disabled="disabled" @mousedown.prevent @click="popoverZ=chatOverlayZIndex($event.currentTarget)"><span class="chat-format-trigger" aria-hidden="true">A</span><span>文字格式</span></el-button></template>
  <div class="chat-format-tools" role="toolbar" aria-label="文字格式选项" @mousedown.prevent>
   <button v-for="tool in tools" :key="tool.label" type="button" :disabled="disabled" :title="tool.label+'（先选中文字）'" :aria-label="tool.label" :style="tool.style" @click="apply(tool)">{{tool.label}}</button>
  </div>
 </el-popover>
 <ChatFormattedInputMirror :field="field" :document="modelValue" :enabled="formatted" />
</template>
<script setup>
import {computed,nextTick,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {applyTextFormat,rebaseTextFormat,formatText,formatRuns,formatColors as c} from '@/utils/chatTextFormat'
import {screenshotParts,screenshotMarker} from '@/utils/screenshotReferences'
import ChatFormattedInputMirror from './ChatFormattedInputMirror.vue'
import {chatOverlayZIndex} from '@/utils/chatOverlay'
const props=defineProps({text:{type:String,default:''},modelValue:Object,input:Object,disabled:Boolean})
const emit=defineEmits(['update:modelValue'])
const visible=ref(false),popoverZ=ref(2101)
const field=computed(()=>props.input?.textarea||props.input?.$el?.querySelector('textarea'))
const tools=[{label:'红字',type:'textColor',color:c.red,style:{color:c.red}},{label:'蓝字',type:'textColor',color:c.blue,style:{color:c.blue}},{label:'浅蓝高亮',type:'highlight',color:c.lightBlue,style:{background:c.lightBlue}},{label:'黄色高亮',type:'highlight',color:c.yellow,style:{background:c.yellow}},{label:'加粗',type:'bold',style:{fontWeight:700}},...[[c.black,'黑'],[c.red,'红'],[c.blue,'蓝']].map(([color,name])=>({label:name+'色下划线',type:'underline',color,style:{textDecoration:'underline',textDecorationColor:color}})),{label:'清除格式',type:'clear'}]
const formatted=computed(()=>formatText(props.modelValue)===props.text&&formatRuns(props.modelValue).some(r=>r.marks.length))
watch(()=>props.text,(value,old)=>{if(formatText(props.modelValue)!==value)emit('update:modelValue',rebaseTextFormat(props.modelValue,old,value))},{flush:'sync'})
function rawOffset(index){let visible=0,raw=0;for(const part of screenshotParts(props.text)){const length=part.token?screenshotMarker.length:part.text.length;if(index<=visible+length)return raw+(part.token?(index===visible?0:part.token.length):index-visible);visible+=length;raw+=(part.token||part.text).length}return raw}
async function apply(tool){const field=props.input?.textarea||props.input?.$el?.querySelector('textarea');if(!field)return
 const start=field.selectionStart,end=field.selectionEnd
 if(start===end){ElMessage.info('请先选中需要设置格式的文字');field.focus();return}
 emit('update:modelValue',applyTextFormat(props.text,props.modelValue,rawOffset(start),rawOffset(end),tool.type,tool.color))
 visible.value=false
 await nextTick();field.focus();field.setSelectionRange(start,end)
}
</script>
<style scoped>
.chat-format-trigger{font-weight:700;text-decoration:underline;text-underline-offset:3px;margin-right:5px}
.chat-format-button.el-button{flex:0 0 auto;width:auto!important;min-width:max-content;max-width:none;white-space:nowrap;margin-left:6px!important;padding-left:10px!important;padding-right:10px!important}
.chat-format-tools{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.chat-format-tools button{border:1px solid #dbe3ee;border-radius:5px;background:white;padding:7px 5px;font-size:12px;cursor:pointer;color:#334155;white-space:nowrap}
.chat-format-tools button:disabled{opacity:.45;cursor:not-allowed}
</style>
<style>.chat-text-format-popover{max-width:calc(100vw - 32px);box-sizing:border-box}</style>
