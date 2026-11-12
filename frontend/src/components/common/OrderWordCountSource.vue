<template>
  <div v-if="sourceLabel || directions.length" class="order-word-count-source">
    <div v-if="sourceLabel" :title="order.wordCountParentOrderNo || undefined">{{ sourceLabel }}</div>
    <div v-for="item in directions" :key="item.languagePair" class="order-word-count-direction">
      {{ compactLanguagePair(item.languagePair) }}：{{ formatWordCountMatrix(item.wordCountMatrix) }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { compactLanguagePair } from '@/utils/languagePair'
import { formatWordCountMatrix } from '@/utils/wordCountMatrix'

const props = defineProps({ order: Object })
const sourceLabel = computed(() => {
  const order = props.order
  if (!order) return ''
  if (order.wordCountMatrixSource === 'suborder_aggregate' || order.source === 'suborder_aggregate') {
    return '由下级子订单汇总'
  }
  if (order.wordCountParentOrderNo) {
    return order.wordCountMatchesParent
      ? '方向子订单 · 字数来自上一级订单'
      : '方向子订单 · 字数与上一级不同'
  }
  return ''
})
const directions = computed(() => props.order?.wordCountByDirection ?? [])
</script>

<style scoped>
.order-word-count-source { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.order-word-count-direction { color: var(--el-text-color-regular); margin-top: 2px; }
</style>
