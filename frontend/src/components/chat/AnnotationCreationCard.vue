<template><section class="annotation-creation-card"><strong>{{ card.title }}</strong><dl><template v-for="field in card.fields" :key="field.label"><dt>{{ field.label }}</dt><dd><ScreenshotText :text="String(display(field)??'')" :chat-message-id="chatMessageId" /></dd></template></dl></section></template>
<script setup>
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { formatBusinessDateTime } from '@/utils/dateTime'
defineProps({card:{type:Object,required:true},chatMessageId:[String,Number]})
const display=field=>field.label==='任务提交时间'&&/^\d{4}-/.test(field.value)?formatBusinessDateTime(field.value):field.value
</script>
<style scoped>.annotation-creation-card{max-width:560px;min-width:min(280px,100%)}.annotation-creation-card>strong{display:block;padding:2px 0 12px;color:#1d4ed8;border-bottom:1px solid #dbeafe}.annotation-creation-card dl{display:grid;grid-template-columns:92px minmax(0,1fr);gap:10px 12px;margin:14px 0 0;font-size:13px;line-height:1.6}.annotation-creation-card dt{color:#64748b}.annotation-creation-card dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:480px){.annotation-creation-card dl{grid-template-columns:76px minmax(0,1fr);gap:8px}}</style>
