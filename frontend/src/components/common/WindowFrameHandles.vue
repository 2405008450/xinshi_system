<template><span ref="anchor" class="window-frame-anchor" /><div v-if="!disabled" class="window-frame-drag" title="按住此区域移动窗口" @mousedown="geometry.start($event)" /><i v-for="edge in disabled?[]:['n','s','w','e','nw','ne','sw','se']" :key="edge" class="app-window-resize" :class="`app-window-resize--${edge}`" @mousedown="geometry.start($event,edge)" /></template>
<script setup>
import { ref,watch } from 'vue'
import { useWindowGeometry } from '@/composables/useWindowGeometry'
defineProps({disabled:Boolean})
const emit=defineEmits(['change']),anchor=ref()
const geometry=useWindowGeometry(()=>anchor.value?.parentElement)
defineExpose({start:geometry.start})
watch(()=>geometry.state.rect,rect=>{if(rect)emit('change',{...rect})},{deep:true,flush:'sync'})
</script>
<style scoped>.window-frame-anchor{display:none}.window-frame-drag{position:absolute;left:0;right:140px;top:0;height:24px;cursor:grab;z-index:9}</style>
