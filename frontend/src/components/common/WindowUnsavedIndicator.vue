<template>
  <button v-if="items.length" type="button" class="window-unsaved-indicator" :class="{'is-all':allNew}" :title="hint" @mousedown.stop @dblclick.stop @click.stop="locateNext" aria-live="polite">
    {{ allNew?'新增内容未保存':'有修改未保存' }}<span>（{{items.length}}处）</span><small v-if="position">{{position}}/{{items.length}}</small>
  </button>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { windowUnsavedItems } from '@/utils/windowUnsavedState'
import { revealFormTarget, scrollFormTarget, focusFormTarget } from '@/utils/formNavigation'
const props=defineProps({root:Object,active:Boolean})
const items=computed(()=>props.active?windowUnsavedItems(props.root):[])
const allNew=computed(()=>items.value.every(item=>item.entry.creating))
const position=ref(0),hint=computed(()=>`点击依次定位未保存内容${items.value.length?'：'+items.value[(position.value||1)-1]?.label:''}；草稿备份不代表正式保存`)
let highlighted,timer,locating=false
watch(()=>items.value.map(item=>item.path+'|'+item.label).join(';'),()=>position.value=0)
function clear(){clearTimeout(timer);highlighted?.classList.remove('window-unsaved-target')}
async function locateNext(){
  if(locating||!items.value.length)return
  locating=true
  try{
    const index=position.value%items.value.length,target=items.value[index].target
    position.value=index+1
    await revealFormTarget(target)
    if(!target?.isConnected)return
    clear();highlighted=target;target.classList.add('window-unsaved-target');scrollFormTarget(target,props.root);focusFormTarget(target)
    timer=setTimeout(clear,2200)
  }finally{locating=false}
}
onBeforeUnmount(clear)
</script>
<style>
.window-unsaved-indicator{display:inline-flex;align-items:center;gap:3px;flex:none;max-width:100%;margin:0 140px 8px 0;padding:4px 9px;border:1px solid #f5c67b;border-radius:5px;background:#fff7e6;color:#9a4c00;font-size:12px;line-height:20px;cursor:pointer}.window-unsaved-indicator.is-all{border-color:#f0a9a9;background:#fff1f0;color:#b42318}.window-unsaved-indicator:focus-visible{outline:2px solid #d97706;outline-offset:2px}.window-unsaved-indicator small{margin-left:5px}.window-unsaved-target{outline:2px solid #f59e0b!important;outline-offset:3px;border-radius:4px;box-shadow:0 0 0 5px #f59e0b18;transition:outline-color .2s}
</style>
