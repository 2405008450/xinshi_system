<template>
  <el-alert v-if="error && !loading" :title="error" type="error" :closable="false">
    <el-button link @click="$emit('retry')">重试</el-button>
  </el-alert>
  <div v-else class="chat-initial-load" role="status">正在加载消息…</div>
</template>

<script setup>
defineProps({ error: String, loading: Boolean })
defineEmits(['retry'])
</script>

<style scoped>
.chat-initial-load {
  display: grid;
  flex: 1;
  place-items: center;
  padding: 16px;
  color: var(--chat-text-muted, #64748b);
}
</style>
