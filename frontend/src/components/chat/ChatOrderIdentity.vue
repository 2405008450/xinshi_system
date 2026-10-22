<template>
  <span v-if="orderNo && ['annotation', 'translation'].includes(projectType)" class="chat-order-identity" :class="{ 'is-child': childOrder, 'has-title': title }">
    <strong v-if="title" class="chat-order-identity__title" :title="title">{{ title }}</strong>
    <span class="chat-order-identity__details">
      <b v-if="childOrder" class="chat-order-identity__badge">{{ orderDepth > 1 ? '孙订单' : '子订单' }}</b>
      <span class="chat-order-identity__number" :title="`订单号：${orderNo}`">{{ orderNo }}</span>
      <ChatProjectManagersSummary v-if="showManagers && projectId" :project-id="projectId" :project-type="projectType" />
    </span>
  </span>
</template>
<script setup>
import { computed } from 'vue'
import ChatProjectManagersSummary from './ChatProjectManagersSummary.vue'
const props = defineProps({ orderNo: { type: String, default: '' }, projectType: { type: String, default: '' }, title: { type: String, default: '' }, projectId: { type: String, default: '' }, showManagers: Boolean })
const orderDepth = computed(() => /^AP-\d{6}-\d+(?:\.\d{3}){1,2}$/.test(props.orderNo) ? props.orderNo.split('.').length - 1 : 0)
const childOrder = computed(() => props.projectType === 'annotation' && orderDepth.value > 0)
</script>
<style scoped>
.chat-order-identity{display:flex;min-width:0;flex-direction:column;gap:5px;user-select:text;cursor:text}
.chat-order-identity__title{display:block;font-size:13px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-order-identity__details{display:flex;align-items:center;flex-wrap:wrap;gap:5px;font-size:11px;color:#64748b;line-height:1.5}
.chat-order-identity__number{overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.chat-order-identity__badge{flex:none;padding:1px 6px;border:1px solid #f59e0b;border-radius:4px;background:#fef3c7;color:#92400e;font-size:11px}
.is-child .chat-order-identity__number{color:#92400e;font-weight:600}
.has-title{gap:2px;min-width:0}
</style>
