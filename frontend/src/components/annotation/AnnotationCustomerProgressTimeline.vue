<template>
  <div class="customer-progress-history" v-loading="loading">
    <el-alert v-if="loadError" :title="loadError" type="warning" :closable="false" show-icon>
      <el-button link type="primary" :disabled="busy || loading" @click="$emit('retry')">重试加载</el-button>
    </el-alert>
    <el-timeline class="customer-progress-timeline">
      <el-timeline-item v-for="row in rows" :key="`customer:${row.id}`" :data-progress-record-id="row.id" data-progress-track="customer" :class="{ 'is-progress-search-target': String(row.id) === String(targetRecordId) }">
        <div class="progress-child-note">{{ row.changeNote }}</div>
        <div class="progress-child-meta">
          <span>{{ formatBusinessDateTimeMinute(row.effectiveOn) }}</span>
          <span>填写人：{{ row.changedByName || '系统' }}</span>
          <el-tag size="small" effect="plain">客户进度</el-tag>
          <template v-if="canWrite">
            <el-button link type="primary" size="small" :disabled="busy" @click="$emit('edit', row)">编辑</el-button>
            <el-button link type="danger" size="small" :disabled="busy" @click="$emit('delete', row)">删除</el-button>
          </template>
        </div>
        <div v-if="row.updatedAt !== row.changedAt" class="progress-child-meta">修改人：{{ row.updatedByName || '系统' }} · {{ formatBusinessDateTimeMinute(row.updatedAt) }}</div>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-if="!loading && !loadError && !rows.length" description="暂无客户进度，可记录客户确认、反馈及后续安排" :image-size="80" />
  </div>
</template>

<script setup>
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
defineProps({ rows: { type: Array, default: () => [] }, loading: Boolean, loadError: String, canWrite: Boolean, busy: Boolean, targetRecordId: String })
defineEmits(['retry', 'edit', 'delete'])
</script>

<style scoped>
.customer-progress-history{min-height:100px}
.customer-progress-timeline{padding-left:8px;margin-top:10px}
.progress-child-note{white-space:pre-wrap;word-break:break-word;line-height:1.6}
.progress-child-meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px;font-size:12px;color:var(--el-text-color-secondary)}
.is-progress-search-target{border-radius:6px;background:var(--el-color-warning-light-9);box-shadow:inset 3px 0 0 var(--el-color-warning)}
</style>
