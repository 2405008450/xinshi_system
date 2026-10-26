<template>
  <el-alert v-if="savedAt" type="info" :closable="false" show-icon class="mail-draft-alert">
    <template #title>已恢复 {{ formatBusinessDateTimeMinute(savedAt) }} 未发送的邮件草稿</template>
    <el-button type="primary" link :disabled="disabled" @click="$emit('reset')">恢复系统默认内容</el-button>
  </el-alert>
</template>

<script setup>
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
defineProps({ savedAt: { type: String, default: '' }, disabled: Boolean })
defineEmits(['reset'])
</script>

<style scoped>
.mail-draft-alert { margin-bottom: 12px; }
</style>
