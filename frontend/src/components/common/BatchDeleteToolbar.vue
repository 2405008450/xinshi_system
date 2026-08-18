<template>
  <div class="batch-delete-toolbar">
    <el-button v-if="!active" type="danger" plain @click="$emit('enter')">
      删除管理
    </el-button>
    <template v-else>
      <el-tag type="danger" effect="plain">删除模式</el-tag>
      <span class="selected-count">已选 {{ selectedCount }} 条</span>
      <el-button :disabled="loading" @click="$emit('exit')">退出</el-button>
      <el-button
        type="danger"
        :disabled="selectedCount === 0"
        :loading="loading"
        @click="$emit('confirm')"
      >
        删除所选（{{ selectedCount }}）
      </el-button>
    </template>
  </div>
</template>

<script setup>
defineProps({
  active: { type: Boolean, default: false },
  selectedCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
})

defineEmits(['enter', 'exit', 'confirm'])
</script>

<style scoped>
.batch-delete-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.batch-delete-toolbar .el-button + .el-button {
  margin-left: 0;
}

.selected-count {
  color: var(--el-text-color-regular);
  font-size: 13px;
}
</style>
