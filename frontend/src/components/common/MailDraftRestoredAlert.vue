<template>
  <el-alert v-if="savedAt || writtenAt" type="info" :closable="false" show-icon class="mail-draft-alert">
    <template #title>{{ savedAt ? "已恢复邮件草稿" : "邮件草稿已保存到本机" }} · {{ formatBusinessDateTimeMinute(writtenAt || savedAt) }}</template>
    <el-button type="primary" link :disabled="disabled" @click="$emit('reset')">恢复系统默认内容</el-button>
  </el-alert>
</template>

<script setup>
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
defineProps({ savedAt: { type: String, default: '' }, writtenAt: String, disabled: Boolean })
defineEmits(['reset'])
</script>

<style scoped>
.mail-draft-alert { margin-bottom: 12px; }
</style>
