<template>
  <div v-if="comparison.name" class="folder-root-comparison" :class="{ 'is-mismatch': mismatch }">
    <div>
      <span>所选文件夹</span>
      <div class="path-value">{{ comparison.selected || comparison.name }}</div>
      <small v-if="!comparison.selected">仅取得所选文件夹名称</small>
      <small v-if="comparison.nameMismatch">所选名称：<b>{{ comparison.name }}</b></small>
    </div>
    <div>
      <span>当前根路径</span>
      <div class="path-value">{{ comparison.entered || '尚未填写' }}</div>
      <small v-if="comparison.nameMismatch">路径末尾：<b>{{ comparison.enteredName || '空' }}</b></small>
    </div>
    <div v-if="mismatch" class="comparison-message" role="alert">
      {{ comparison.nameMismatch ? '末尾名称不一致，请核对路径或重新选择文件夹。' : '完整路径与所选文件夹不同，请核对。' }}
      <el-button v-if="comparison.selected && canRestore" link type="primary" @click="$emit('restore')">使用所选完整路径</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ comparison: { type: Object, required: true }, canRestore: Boolean })
defineEmits(['restore'])
const mismatch = computed(() => props.comparison.nameMismatch || props.comparison.pathMismatch)
</script>

<style scoped>
.folder-root-comparison { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 8px 20px; padding: 10px 12px; border: 1px solid var(--el-border-color); border-radius: 6px; background: var(--el-fill-color-lighter); }
.folder-root-comparison.is-mismatch { border-color: var(--el-color-danger-light-5); }
.folder-root-comparison span, .folder-root-comparison small { color: var(--el-text-color-secondary); font-size: 12px; }
.path-value { overflow-wrap: anywhere; user-select: text; }
.comparison-message { grid-column: 1 / -1; color: var(--el-color-danger); }
.is-mismatch b { color: var(--el-color-danger); }
.comparison-message .el-button { margin-left: 8px; }
</style>
