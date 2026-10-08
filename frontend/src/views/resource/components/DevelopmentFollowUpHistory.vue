<template>
  <section class="follow-up-history" data-dialog-field-search-label="历史跟进记录">
    <h4>历史跟进记录 <span>{{ entries.length }} 条</span></h4>
    <el-descriptions v-for="entry in entries" :key="entry.id" :column="2" border size="small">
      <el-descriptions-item label="跟进内容" :span="2">{{ entry.content }}</el-descriptions-item>
      <el-descriptions-item label="操作人">{{ entry.operator_name || '-' }}</el-descriptions-item>
      <el-descriptions-item label="操作时间">{{ followUpTime(entry.created_at) }}</el-descriptions-item>
    </el-descriptions>
    <el-descriptions v-if="legacy" :column="2" border size="small">
      <el-descriptions-item label="历史跟进原文" :span="2">{{ legacy }}</el-descriptions-item>
    </el-descriptions>
    <p v-if="!entries.length && !legacy" class="muted">暂无历史跟进记录</p>
  </section>
</template>

<script setup>
import { followUpTime } from '@/utils/resourceDevelopment'
defineProps({ entries: { type: Array, default: () => [] }, legacy: { type: String, default: '' } })
</script>

<style scoped>
.follow-up-history h4{margin:16px 0 10px;font-size:14px}
.follow-up-history h4 span{font-size:12px;font-weight:400;color:var(--el-text-color-secondary)}
.follow-up-history .el-descriptions{margin-bottom:12px}
.follow-up-history :deep(.el-descriptions__table){table-layout:fixed;width:100%}
.follow-up-history :deep(.el-descriptions__content){white-space:pre-wrap;overflow-wrap:anywhere}
</style>
