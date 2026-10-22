<template>
  <section class="chat-time-settings" aria-label="聊天设置">
    <el-button text class="chat-time-settings__toggle" :aria-expanded="expanded" @click="expanded = !expanded">时间显示</el-button>
    <div v-if="expanded" class="chat-time-settings__options">
      <el-radio-group v-model="mode" aria-label="时间显示方式">
        <el-radio value="full">完整显示（默认）</el-radio>
        <el-radio value="hidden">不显示时间</el-radio>
        <el-radio value="no-year">不显示年份</el-radio>
        <el-radio value="time">不显示年份和日期</el-radio>
      </el-radio-group>
      <p>适用于所有会话，按当前账号保存。</p>
    </div>
  </section>
</template>
<script setup>
import { ref } from 'vue'
import { useChatTimeDisplay } from '@/composables/useChatTimeDisplay'
const expanded = ref(false)
const { mode } = useChatTimeDisplay()
</script>
<style scoped>
.chat-time-settings{padding:12px;min-height:0;overflow-y:auto}
.chat-time-settings__toggle{width:100%;justify-content:flex-start;font-weight:600}
.chat-time-settings__options{padding:6px 10px}
.chat-time-settings__options .el-radio-group{display:flex;flex-direction:column;align-items:flex-start;gap:6px}
.chat-time-settings__options .el-radio{margin:0;white-space:normal;height:auto;min-height:32px}
.chat-time-settings__options p{color:#94a3b8;font-size:11px;line-height:1.6}
</style>
