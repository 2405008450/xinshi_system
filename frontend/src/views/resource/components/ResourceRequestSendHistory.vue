<template>
  <div class="request-send-history" aria-label="发送记录">
    <div class="request-send-history__heading">
      <strong>发送记录</strong>
      <span>已发送 {{ records.length }}/{{ limit }} 次</span>
    </div>
    <p v-if="!records.length">暂无发送记录</p>
    <div v-for="(item,index) in visibleRecords" :key="item.id" class="request-send-history__item">
      <span><em v-if="index===0" class="request-send-history__latest">最新</em>第 {{ item.number }} 次 · {{ item.senderName }} · {{ formatTime(item.sentAt) }}</span>
      <small v-if="item.recipients?.length">接收人：{{ item.recipients.join('、') }}　已收到 {{ item.receivedCount }}/{{ item.recipients.length }} · 已处理 {{ item.processedCount }}/{{ item.recipients.length }}</small>
      <template v-if="item.cancellation"><small>已取消 · {{ item.cancellation.cancelledBy }} · {{ formatTime(item.cancellation.cancelledAt) }}　取消通知已确认 {{ item.cancellation.confirmedCount }}/{{ item.cancellation.recipients.length }}</small><details><summary>查看取消确认记录</summary><div v-for="person in item.cancellation.recipients" :key="person.userId">{{ person.name }}：{{ person.confirmedAt ? '确认收到取消通知 · '+formatTime(person.confirmedAt) : '待确认收到取消通知' }}</div></details></template>
      <template v-if="item.executionReplies?.length"><small>执行平台：{{ [...new Set(item.executionReplies.flatMap(r=>r.platforms.map(p=>p.name)))].join('、') }}</small><details><summary>查看执行回执（{{ item.executionReplies.length }} 条）</summary><RequestExecutionReplies :rows="item.executionReplies" /></details></template>
    </div>
    <button v-if="records.length > 1" type="button" class="request-send-history__toggle" :aria-expanded="expanded" @click="expanded=!expanded">
      <span aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>{{ expanded ? '收起发送记录' : `展开其余 ${records.length-1} 条发送记录` }}
    </button>
  </div>
</template>
<script setup>
import RequestExecutionReplies from './RequestExecutionReplies.vue'
import { computed,ref,watch } from 'vue'
import { formatBusinessDateTime as formatTime } from '@/utils/dateTime'
const props=defineProps({records:{type:Array,default:()=>[]},limit:{type:Number,default:5}})
const expanded=ref(false)
// 每个发送方式的批次序号由后端按时间顺序生成，复制后倒序，不改变原数据。
const sortedRecords=computed(()=>[...props.records].sort((a,b)=>Number(b.number)-Number(a.number)))
const visibleRecords=computed(()=>expanded.value ? sortedRecords.value : sortedRecords.value.slice(0,1))
watch(()=>props.records.map(item=>item.id).join('|'),()=>{expanded.value=false})
</script>
<style scoped>
.request-send-history{width:100%;margin-top:12px;border-top:1px solid #e2e8f0;padding-top:10px;font-size:12px;color:#475569}.request-send-history__heading{display:flex;justify-content:space-between;gap:12px}.request-send-history p{margin:8px 0;color:#94a3b8}.request-send-history__item{padding:8px 0;line-height:1.7;border-bottom:1px dashed #e2e8f0;overflow-wrap:anywhere}.request-send-history__item small{display:block;color:#64748b}.request-send-history__latest{display:inline-block;margin-right:6px;padding:0 5px;border-radius:3px;background:#eff6ff;color:#2563eb;font-size:11px;font-style:normal}.request-send-history__toggle{display:flex;align-items:center;gap:4px;margin-top:8px;padding:3px 0;border:0;background:transparent;color:var(--el-color-primary);font:inherit;cursor:pointer}.request-send-history__toggle:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:3px}
</style>
