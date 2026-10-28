<template>
  <span class="chat-presence" :title="scheduleTitle">
    <span class="chat-desktop-presence" :class="{ 'is-online': online === true }">{{ online === true ? '电脑端在线' : online === false ? '电脑端离线' : loading ? '检测中' : '状态未知' }}</span>
    <span class="chat-work-presence" :class="{ 'is-working': workStatus?.workState === 'working' }">{{ workLabel }}</span>
    <span v-if="online === true && workStatus?.workState === 'off_hours'" class="chat-overtime-presence">加班中</span>
  </span>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ online: { type: Boolean, default: undefined }, loading: Boolean, workStatus: Object })
const workLabel = computed(() => ({ working: '工作时间', off_hours: '非工作时间', unscheduled: '未排班' })[props.workStatus?.workState] || (props.loading ? '班次检测中' : '班次未知'))
const scheduleTitle = computed(() => [
  '电脑在线依据实时连接或最近120秒的电脑端心跳；无记录时显示未知，不代表已读',
  '加班中表示非班次时间电脑在线',
  props.workStatus?.shiftLabel,
  props.workStatus?.shiftPeriods?.join('、'),
  '按班次安排及 UTC+8 判断',
].filter(Boolean).join(' · '))
</script>
<style scoped>
.chat-presence{display:inline-flex;align-items:center;flex-wrap:wrap;gap:4px 8px;font-size:11px;line-height:1.5}
.chat-desktop-presence,.chat-work-presence,.chat-overtime-presence{white-space:nowrap;color:#64748b}
.chat-desktop-presence.is-online,.chat-work-presence.is-working{color:#15803d}
.chat-desktop-presence::before{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;background:currentColor;margin-right:4px;vertical-align:middle}
.chat-overtime-presence{color:#b45309;border:1px solid #fcd34d;border-radius:4px;padding:0 4px}
</style>
