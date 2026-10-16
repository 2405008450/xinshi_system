<template>
  <el-timeline class="manager-change-timeline" aria-label="负责人变更时间轴">
    <el-timeline-item v-for="row in rows" :key="row.id" class="manager-change-event"
      :data-change-id="row.id" :data-project-id="row.projectId" :data-manager-role="row.managerRole">
      <template #dot><span class="manager-change-dot" /></template>
      <div class="manager-change-heading">
        <strong>{{ roleLabel(row.managerRole) }}：{{ changeText(row) }}</strong>
        <el-tag size="small" effect="plain">{{ modeLabel(row.changeMode) }}</el-tag>
      </div>
      <div class="manager-change-meta">
        <time :datetime="row.changedAt">{{ formatBusinessDateTime(row.changedAt) }}</time>
        <span>操作人：{{ row.actorNameSnapshot || row.actorUsernameSnapshot || '系统' }}</span>
      </div>
      <div class="manager-change-project">
        <div class="manager-change-project-text">
          <span class="manager-change-order">{{ row.orderNo }}</span>
          <span>{{ row.projectName || '-' }}</span>
        </div>
        <el-button v-if="!projectId" link type="primary" size="small" @click="$emit('filter-project', row)">仅看该项目</el-button>
      </div>
      <div class="manager-change-reason">
        <span class="manager-change-reason-label">调整原因</span>
        <div>{{ row.reason?.trim() || '-' }}</div>
      </div>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup>
import { formatBusinessDateTime } from '@/utils/dateTime'

defineProps({ rows: { type: Array, default: () => [] }, projectId: { type: String, default: '' } })
defineEmits(['filter-project'])

const roleLabel = role => ({ client_manager: '客户经理', project_manager: '项目经理' }[role] || '负责人')
const modeLabel = mode => ({ direct_transfer: '批量交接', inline_edit: '列表直接修改', project_edit: '编辑项目', inheritance: '上级同步' }[mode] || '其他变更')
const changeText = row => {
  if (row.managerRole === 'client_manager') {
    const previous = row.previousManagerId ? (row.previousManagerName || '原负责人') : '未分配'
    const next = row.newManagerId ? (row.newManagerName || '新负责人') : '未分配'
    return `${previous} → ${next}`
  }
  if (row.previousManagerId && row.newManagerId) return `${row.previousManagerName || '原负责人'} → ${row.newManagerName || '新负责人'}`
  if (row.newManagerId) return `新增 ${row.newManagerName || '新负责人'}`
  if (row.previousManagerId) return `移除 ${row.previousManagerName || '原负责人'}`
  return '负责人调整'
}
</script>

<style scoped>
.manager-change-timeline{margin:0;padding:10px 4px 0 8px}
.manager-change-event{padding-bottom:24px}
.manager-change-dot{display:block;width:14px;height:14px;border:3px solid var(--el-color-primary-light-5);border-radius:50%;background:var(--el-color-primary);box-sizing:border-box}
.manager-change-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap;line-height:1.6}
.manager-change-heading strong{font-size:15px;color:var(--el-text-color-primary);overflow-wrap:anywhere}
.manager-change-meta{display:flex;align-items:center;gap:8px 16px;flex-wrap:wrap;margin-top:5px;font-size:12px;color:var(--el-text-color-secondary)}
.manager-change-meta time{font-variant-numeric:tabular-nums}
.manager-change-project{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-top:10px}
.manager-change-project-text{display:flex;gap:4px 12px;flex-wrap:wrap;min-width:0;line-height:1.6;color:var(--el-text-color-regular);overflow-wrap:anywhere}
.manager-change-order{color:var(--el-color-primary);font-variant-numeric:tabular-nums}
.manager-change-project .el-button{flex:none}
.manager-change-reason{margin-top:10px;padding-left:12px;border-left:2px solid var(--el-border-color-light);color:var(--el-text-color-primary);line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
.manager-change-reason-label{font-size:12px;color:var(--el-text-color-secondary)}
@media(max-width:600px){.manager-change-project{flex-direction:column;gap:4px}.manager-change-project-text{flex-direction:column}.manager-change-heading strong{font-size:14px}}
</style>
