<template>
  <Teleport to="body">
    <div v-if="visible" ref="menu" class="field-copy-menu" role="menu" aria-label="字段复制菜单"
      :style="{left:position.x+'px',top:position.y+'px'}" @mousedown.prevent @contextmenu.prevent @keydown.esc.prevent.stop="close">
      <button type="button" role="menuitem" @click="copy"><el-icon><CopyDocument /></el-icon>复制</button>
      <span>{{selected ? '复制选中内容' : '复制整个字段'}}</span>
    </div>
  </Teleport>
</template>
<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { copyTextToClipboard } from '@/utils/clipboard'
import { fieldCopyScope, selectedFieldText, wholeFieldText } from '@/utils/fieldCopy'
const visible=ref(false),selected=ref(false),menu=ref()
const position=reactive({x:0,y:0})
let text='',origin,pendingSelection
function close(){visible.value=false;text=''}
async function open(event){
  const scope=fieldCopyScope(event.target)
  if(!scope)return
  const selection=pendingSelection?.scope===scope ? pendingSelection.text : selectedFieldText(scope,event.target)
  pendingSelection=undefined
  const value=selection||wholeFieldText(scope)
  if(!value)return
  event.preventDefault();event.stopPropagation()
  text=value;selected.value=!!selection;origin=event.target
  const rect=scope.getBoundingClientRect()
  position.x=event.clientX||rect.left;position.y=event.clientY||rect.bottom
  visible.value=true
  await nextTick()
  if(!menu.value)return
  const bounds=menu.value.getBoundingClientRect()
  position.x=Math.max(8,Math.min(position.x,window.innerWidth-bounds.width-8))
  position.y=Math.max(8,Math.min(position.y,window.innerHeight-bounds.height-8))
  menu.value.querySelector('button')?.focus({preventScroll:true})
}
async function copy(){
  const value=text
  close()
  if(await copyTextToClipboard(value))ElMessage.success('已复制')
  else ElMessage.error('复制失败，请选中文字后按 Ctrl+C')
  if(origin?.isConnected)origin.focus?.({preventScroll:true})
}
function dismiss(event){if(visible.value&&!menu.value?.contains(event.target))close()}
function rememberSelection(event){
  pendingSelection=undefined
  if(event.button!==2)return
  const scope=fieldCopyScope(event.target)
  if(scope)pendingSelection={scope,text:selectedFieldText(scope,event.target)}
}
function keydown(event){
  if(event.key==='Escape')close()
  else if(event.key==='ContextMenu'||event.key==='F10'&&event.shiftKey)void open(event)
}
onMounted(()=>{
  document.addEventListener('contextmenu',open,true)
  document.addEventListener('pointerdown',rememberSelection,true)
  document.addEventListener('mousedown',dismiss,true)
  document.addEventListener('keydown',keydown,true)
  document.addEventListener('scroll',close,true)
  window.addEventListener('resize',close)
  window.addEventListener('auth-session-clearing',close)
})
onBeforeUnmount(()=>{
  document.removeEventListener('contextmenu',open,true)
  document.removeEventListener('pointerdown',rememberSelection,true)
  document.removeEventListener('mousedown',dismiss,true)
  document.removeEventListener('keydown',keydown,true)
  document.removeEventListener('scroll',close,true)
  window.removeEventListener('resize',close)
  window.removeEventListener('auth-session-clearing',close)
})
</script>
<style>
.field-copy-menu{position:fixed;z-index:2147483647;min-width:164px;padding:6px;border:1px solid var(--el-border-color-light);border-radius:8px;background:var(--el-bg-color-overlay,#fff);box-shadow:var(--el-box-shadow-light);color:var(--el-text-color-primary)}
.field-copy-menu button{display:flex;align-items:center;gap:8px;width:100%;padding:8px 12px;border:0;border-radius:4px;background:transparent;color:inherit;text-align:left;cursor:pointer}
.field-copy-menu button:hover,.field-copy-menu button:focus-visible{background:var(--el-color-primary-light-9);color:var(--el-color-primary)}
.field-copy-menu>span{display:block;padding:0 12px 5px;font-size:12px;color:var(--el-text-color-secondary)}
.app-field-copy-cell,.client-management-link{user-select:text!important}
</style>
