<template>
  <div v-loading="loading" class="department-shift-panel">
    <template v-if="hasDepartment">
      <el-table v-if="visibleMembers.length" :data="visibleMembers" border size="small" class="data-table">
        <el-table-column prop="name" label="同事" min-width="120" show-overflow-tooltip />
        <el-table-column label="班次" min-width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(dayOf(row))" size="small" effect="plain">{{ dayOf(row)?.shift_label || '未安排' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="140">
          <template #default="{ row }">{{ timeText(dayOf(row)) || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="140">
          <template #default="{ row }">
            <div class="status-tags">
              <el-tag v-if="dayOf(row)?.on_leave" type="danger" size="small">{{ dayOf(row)?.leave_type || '请假中' }}</el-tag>
              <el-tag v-else-if="dayOf(row)?.shift_code === 'weekend_duty'" type="danger" size="small">周末值班</el-tag>
              <el-tag v-else-if="dayOf(row)?.source === 'override'" type="warning" size="small">临时调整</el-tag>
              <el-tag v-if="dayOf(row)?.is_locked" type="primary" size="small" effect="plain">固定班次</el-tag>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="empty-tip">当前部门暂无其他同事排班。</div>

    </template>
    <div v-else class="empty-tip">你尚未设置部门，无法展示部门班次。</div>

    <el-collapse v-if="leaveRecords.length" class="future-leave">
      <el-collapse-item :title="`全公司未来 30 天请假（${leaveRecords.length}）`" name="future-leave">
        <el-table :data="leaveRecords" border size="small" class="data-table">
          <el-table-column prop="employee_name" label="员工" width="120" />
          <el-table-column prop="department" label="部门" width="140">
            <template #default="{ row }">{{ row.department || '-' }}</template>
          </el-table-column>
          <el-table-column label="开始时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.start_date) }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.end_date) }}</template>
          </el-table-column>
          <el-table-column prop="leave_type" label="请假类型" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'danger' : 'warning'" size="small">{{ row.status === 'active' ? '请假中' : '即将请假' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        </el-table>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  departmentMembers: { type: Array, default: () => [] },
  leaveRecords: { type: Array, default: () => [] },
  date: { type: String, default: '' },
  myDepartment: { type: String, default: '' }
})

const hasDepartment = computed(() => Boolean(props.myDepartment))

const visibleMembers = computed(() => props.departmentMembers)

function dayOf(row) {
  return row?.days?.[0] || null
}
function timeText(day) {
  if (!day || !day.start_time || !day.end_time) return ''
  return `${day.start_time}–${day.end_time}`
}
function tagType(day) {
  const code = day?.shift_code
  if (!day || code === 'unassigned') return 'warning'
  if (code === 'off') return 'info'
  if (code === 'weekend_duty') return 'danger'
  return 'success'
}
function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.department-shift-panel {
  min-height: 48px;
}

.data-table {
  margin-bottom: 12px;
}

.status-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.future-leave {
  margin-top: 4px;
}

.empty-tip {
  padding: 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.department-shift-panel :deep(.el-table__empty-block) {
  min-height: 48px;
}
</style>
