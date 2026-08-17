<template>
  <div class="path-action-buttons">
    <el-button
      v-if="showOpen"
      type="primary"
      size="small"
      link
      title="打开路径"
      :disabled="disabled"
      @click.stop="$emit('open')"
    >
      <svg viewBox="0 0 1024 1024" width="14" height="14" fill="currentColor" aria-hidden="true">
        <path d="M928 256H512L416 160H128a96 96 0 0 0-96 96v544a96 96 0 0 0 96 96h800a96 96 0 0 0 96-96V352a96 96 0 0 0-96-96zM128 256h249.6l64 64H128V256zm800 544H128V448h800v352z" />
      </svg>
    </el-button>
    <el-button
      v-if="showCopy"
      type="primary"
      size="small"
      link
      title="复制路径"
      :disabled="disabled"
      @click.stop="$emit('copy')"
    >
      <svg viewBox="0 0 1024 1024" width="14" height="14" fill="currentColor" aria-hidden="true">
        <path d="M768 128H256a64 64 0 0 0-64 64v512a64 64 0 0 0 64 64h512a64 64 0 0 0 64-64V192a64 64 0 0 0-64-64zm0 576H256V192h512v512zM640 832v64a64 64 0 0 1-64 64H160a64 64 0 0 1-64-64V384a64 64 0 0 1 64-64h64v64H160v512h416v-64h64z" />
      </svg>
    </el-button>
  </div>
</template>

<script setup>
defineProps({
  showOpen: { type: Boolean, default: true },
  showCopy: { type: Boolean, default: true },
  disabled: Boolean,
})

defineEmits(['open', 'copy'])
</script>

<style scoped>
.path-action-buttons {
  display: inline-flex;
  width: 46px;
  min-width: 46px;
  flex: none;
  align-items: center;
  gap: 2px;
}

.path-action-buttons .el-button {
  width: 22px;
  height: 22px;
  margin-left: 0;
  padding: 0;
}
</style>
