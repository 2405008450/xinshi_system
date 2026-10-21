<template>
  <section v-if="standalone" class="office-editor-page" aria-label="独立文档编辑器">
    <header class="office-page-header"><slot name="header" /><slot name="actions" /></header>
    <main class="office-page-body"><slot /></main>
    <footer v-if="$slots.footer" class="office-page-footer"><slot name="footer" /></footer>
  </section>
  <DraggableFormDialog v-else :model-value="open" width="min(1400px, calc(100vw - 32px))" top="5vh"
    append-to-body destroy-on-close maximizable class="material-office-dialog" :close-on-click-modal="false"
    :before-close="beforeClose" @update:model-value="value => { if (!value) $emit('close') }">
    <template #header><slot name="header" /></template>
    <slot />
    <template #footer><slot name="footer" /></template>
  </DraggableFormDialog>
</template>

<script setup>
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
defineProps({ standalone: Boolean, open: Boolean, beforeClose: Function })
defineEmits(['close'])
</script>

<style scoped>
.office-editor-page { display: flex; flex-direction: column; width: 100%; height: 100%; min-height: 0; background: white; }
.office-page-header { display: flex; align-items: center; gap: 12px; padding: 6px 12px; border-bottom: 1px solid var(--el-border-color-lighter); flex-shrink: 0; }
.office-page-body { flex: 1; min-height: 0; overflow-y: auto; }
.office-page-footer { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px 12px; border-top: 1px solid var(--el-border-color-lighter); background: #f8fafc; flex-shrink: 0; }
@media (max-width: 600px) { .office-page-header { flex-wrap: wrap; gap: 4px 8px; } .office-page-footer { justify-content: flex-end; } }
</style>
