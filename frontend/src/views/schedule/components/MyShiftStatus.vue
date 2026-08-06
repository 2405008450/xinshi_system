<template>
  <div class="my-shift-status" :class="statusClass">
    <template v-if="loading">
      <span class="my-shift-status__eyebrow">我的班次</span>
      <span class="my-shift-status__placeholder">班次加载中…</span>
    </template>
    <template v-else-if="day">
      <span class="my-shift-status__eyebrow">我的班次</span>
      <strong class="my-shift-status__label">{{ day.shift_label || '未安排' }}</strong>
      <span v-if="timeText" class="my-shift-status__time">{{ timeText }}</span>
      <el-tag v-if="day.on_leave" type="danger" size="small" effect="plain">{{ leaveStatusText }}</el-tag>
      <el-tag v-else-if="day.shift_code === 'weekend_duty'" type="danger" size="small" effect="plain">周末值班</el-tag>
      <el-tag v-else-if="day.source === 'override'" type="warning" size="small" effect="plain">临时调整</el-tag>
      <el-tag v-if="day.is_locked && !day.on_leave" type="primary" size="small" effect="plain">固定班次</el-tag>
    </template>
    <template v-else>
      <span class="my-shift-status__eyebrow">我的班次</span>
      <span class="my-shift-status__placeholder">未安排</span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  day: { type: Object, default: null }
})

const timeText = computed(() => {
  const day = props.day
  if (!day || !day.start_time || !day.end_time) return ''
  return `${day.start_time}–${day.end_time}`
})

const leaveStatusText = computed(() => {
  const day = props.day
  const leaveType = day?.leave_type || '请假'
  if (!day?.leave_end) return leaveType
  const end = new Date(day.leave_end)
  if (Number.isNaN(end.getTime())) return leaveType
  const month = String(end.getMonth() + 1).padStart(2, '0')
  const date = String(end.getDate()).padStart(2, '0')
  const hour = String(end.getHours()).padStart(2, '0')
  const minute = String(end.getMinutes()).padStart(2, '0')
  return `${leaveType} · 至 ${month}-${date} ${hour}:${minute}`
})

const statusClass = computed(() => {
  const code = props.day?.shift_code
  if (props.day?.on_leave) return 'is-leave'
  if (code === 'weekend_duty') return 'is-weekend'
  if (code === 'off' || code === 'unassigned') return 'is-off'
  return ''
})
</script>

<style scoped>
.my-shift-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  min-height: 30px;
  border-radius: 6px;
  border: 1px solid var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
  white-space: nowrap;
}

.my-shift-status__eyebrow {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.my-shift-status__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.my-shift-status__time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.my-shift-status__placeholder {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  min-width: 56px;
}

.my-shift-status.is-leave {
  border-color: var(--el-color-danger-light-7);
  background: var(--el-color-danger-light-9);
}

.my-shift-status.is-weekend {
  border-color: var(--el-color-danger-light-7);
  background: var(--el-color-danger-light-9);
}

.my-shift-status.is-off {
  border-color: var(--el-border-color);
  background: var(--el-fill-color-light);
}

@media (max-width: 720px) {
  .my-shift-status {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
    white-space: normal;
  }
}
</style>
