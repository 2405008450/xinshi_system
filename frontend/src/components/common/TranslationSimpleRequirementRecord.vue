<template>
  <article class="requirement-record">
    <div class="requirement-meta"><strong>{{ item.actor_name }}</strong><time>{{ formatBusinessDateTime(item.created_at) }}</time></div>
    <div class="requirement-meta"><span>状态：{{ status(item.previous_status) }} → {{ status(item.saved_status) }}</span><el-tag size="small" :type="item.chargeable ? 'warning' : 'info'">{{ item.chargeable ? '收费' : '不收费' }}</el-tag></div>
    <div class="requirement-texts"><section><strong>原文</strong><p>{{ item.original_text || '-' }}</p></section><section><strong>译文</strong><p>{{ item.translated_text || '-' }}</p></section></div>
    <p v-if="hasCounts(item.word_count_matrix)" class="requirement-added-counts">已加入简单需求字数：{{ formatWordCountMatrix(item.word_count_matrix) }}</p>
    <TranslationRequirementReceipts v-if="showReceipts" :recipients="item.recipients" />
  </article>
</template>
<script setup>
import { formatBusinessDateTime } from '@/utils/dateTime'
import {formatWordCountMatrix} from '@/utils/wordCountMatrix'
const hasCounts=matrix=>matrix&&Object.values(matrix).some(values=>Object.values(values||{}).some(value=>value!==null&&value!==undefined))
import { getProjectStatusLabel } from '@/utils/projectStatus'
import TranslationRequirementReceipts from './TranslationRequirementReceipts.vue'
defineProps({ item: { type: Object, required: true }, showReceipts:{type:Boolean,default:true} })
const status = value => getProjectStatusLabel('translation', value)
</script>
<style scoped>
.requirement-record{padding:12px 0;border-bottom:1px solid var(--el-border-color-lighter);overflow-wrap:anywhere}.requirement-meta{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:8px;color:var(--el-text-color-secondary);font-size:12px}.requirement-texts{display:grid;grid-template-columns:1fr 1fr;gap:16px}.requirement-texts p{white-space:pre-wrap;line-height:1.6;margin:6px 0}.requirement-receipts{margin-top:8px;font-size:12px;line-height:1.8}@media(max-width:650px){.requirement-texts{grid-template-columns:1fr}}
</style>
