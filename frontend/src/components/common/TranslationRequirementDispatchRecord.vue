<template>
  <article class="dispatch-record"><div class="dispatch-meta"><strong>{{item.actor_name}} · 项目经理安排</strong><time>{{time(item.created_at)}}</time></div><p>发送时客户回稿时间：{{time(item.customer_deadline_time)}}</p><strong>安排具体内容（共同可见）</strong><p class="dispatch-content">{{item.content}}</p><TranslationRequirementReceipts :recipients="item.recipients" /><details v-if="item.requirement_snapshot"><summary>发送时关联的简单需求</summary><TranslationSimpleRequirementRecord :item="item.requirement_snapshot" :show-receipts="false" /></details></article>
</template>
<script setup>
import {formatBusinessDateTime as time} from '@/utils/dateTime'
import TranslationRequirementReceipts from './TranslationRequirementReceipts.vue'
import TranslationSimpleRequirementRecord from './TranslationSimpleRequirementRecord.vue'
defineProps({item:{type:Object,required:true}})
</script>
<style scoped>.dispatch-record{padding:12px 0;border-bottom:1px solid var(--el-border-color-lighter);overflow-wrap:anywhere}.dispatch-meta{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--el-text-color-secondary)}.dispatch-content{white-space:pre-wrap;line-height:1.7}.dispatch-record details{margin:10px 0}</style>
