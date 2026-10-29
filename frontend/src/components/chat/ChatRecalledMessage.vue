<template>
  <div class="chat-recalled-message">
    <span>{{ message.recallLabel || `${message.senderName || ''}撤回了一条消息` }}</span>
    <el-button v-if="canReedit" link type="primary" size="small" :disabled="disabled" @click.stop="$emit('reedit', message)">重新编辑</el-button>
  </div>
</template>
<script setup>
defineProps({ message: { type: Object, required: true }, canReedit: Boolean, disabled: Boolean })
defineEmits(['reedit'])
</script>
<style scoped>.chat-recalled-message{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:8px;padding:8px;color:#94a3b8;font-size:12px;line-height:1.5}.chat-recalled-message .el-button{margin:0}</style>
