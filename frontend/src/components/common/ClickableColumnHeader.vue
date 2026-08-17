<template>
  <span class="business-clickable-column-header">
    <span>{{ label }}</span>
    <el-tooltip :content="hint" placement="top">
      <el-icon class="business-clickable-column-hint" aria-label="该列内容可点击"><View /></el-icon>
    </el-tooltip>
  </span>
</template>

<script setup>
import { View } from '@element-plus/icons-vue'

defineProps({
  label: { type: String, required: true },
  hint: { type: String, required: true },
})
</script>

<style>
.business-clickable-column-header { display: inline-flex; align-items: center; gap: 4px; }
.business-clickable-column-hint { color: var(--el-color-primary); font-size: 14px; cursor: help; opacity: 0.85; }
.business-clickable-cell { font-weight: 500; }
.business-clickable-cell:hover { text-decoration: underline; text-underline-offset: 3px; }
</style>
