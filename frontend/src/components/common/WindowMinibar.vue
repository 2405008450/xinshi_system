<script>
import { reactive } from 'vue'
const windows = reactive([])
</script>
<script setup>
import { computed, onBeforeUnmount } from 'vue'
defineProps({ title: { type: String, default: '窗口' } })
defineEmits(['restore', 'close'])
const key = Symbol('window')
windows.push(key)
const bottom = computed(() => `${12 + windows.indexOf(key) * 46}px`)
onBeforeUnmount(() => { const index = windows.indexOf(key); if (index >= 0) windows.splice(index, 1) })
</script>
<template>
  <Teleport to="body">
    <div class="app-window-minibar" :style="{ right: '16px', bottom }" @mousedown.stop @mouseup.stop @click.stop>
      <button type="button" @click="$emit('restore')">{{ title }} · 还原</button>
      <button type="button" aria-label="关闭已最小化窗口" @click="$emit('close')">×</button>
    </div>
  </Teleport>
</template>
