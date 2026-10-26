<template>
  <div class="app-window-controls" @mousedown.stop @pointerdown.stop @dblclick.stop>
    <button type="button" title="最小化" aria-label="最小化窗口" @click="$emit('minimize')">−</button>
    <button v-if="!maximized" type="button" title="最大化" aria-label="最大化窗口" @click="$emit('maximize')">□</button>
    <button v-else type="button" title="还原" aria-label="还原窗口" @click="$emit('restore')">▣</button>
    <button type="button" title="关闭" aria-label="关闭窗口" @click="$emit('close')">×</button>
  </div>
</template>

<script setup>
defineProps({ maximized: Boolean })
defineEmits(['minimize', 'maximize', 'restore', 'close'])
</script>
