<template>
  <section class="development-demand-panel">
    <ResourceRequests ref="requestsRef" embedded arrangement-mode @arrangement-saved="day => emit('saved', day)" @requests-changed="emit('changed')" />
  </section>
</template>
<script setup>
import { defineAsyncComponent, ref } from 'vue'
const ResourceRequests = defineAsyncComponent(() => import('../ResourceRequests.vue'))
const requestsRef = ref()
const emit = defineEmits(['saved', 'changed'])
defineExpose({ reload: () => requestsRef.value?.reload() })
</script>
<style scoped>
.development-demand-panel { padding-bottom: 20px; margin-bottom: 20px; border-bottom: 1px solid var(--el-border-color-light); }
</style>
