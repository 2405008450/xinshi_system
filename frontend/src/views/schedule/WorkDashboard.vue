<template>
  <el-card>
    <template #header>
      <ScheduleHeader
        title="我的工作台"
        :model-value="scheduleDate"
        :weekday-label="weekdayLabel"
        :show-admin-actions="false"
        :readonly="false"
        @update:model-value="scheduleDate = $event"
        @change="onDateChange"
      />
    </template>

    <div class="dashboard-flow">
      <section class="section-block">
        <h3 class="section-title">我的任务</h3>
        <MyTasksPanel
          :current-user-name="currentUserName"
          :tasks-list="workflowTasks"
          :reference-date="scheduleDate"
          @enter-project="handleEnterProject"
        />
      </section>

      <section class="section-block">
        <ShiftTableReadonly :data="shiftTableData" />
      </section>

      <section class="section-block info-block">
        <h4 class="section-title">请假管理</h4>
        <p class="section-desc">仅显示未来一个月的请假信息</p>
        <el-table v-if="leaveRecords.length" :data="leaveRecords" border size="small" class="data-table">
          <el-table-column prop="employee_name" label="员工" width="100" />
          <el-table-column label="开始时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.start_date) }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.end_date) }}</template>
          </el-table-column>
          <el-table-column prop="leave_type" label="类型" width="100" />
          <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
        </el-table>
        <div v-else class="empty-tip">暂无未来一个月的请假信息</div>
      </section>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ScheduleHeader from './components/ScheduleHeader.vue'
import MyTasksPanel from './components/MyTasksPanel.vue'
import ShiftTableReadonly from './components/ShiftTableReadonly.vue'
import { getSchedule } from '@/api/schedule'
import { getMyTasksAPI } from '@/api/workflow'
import { getLeaveRecords } from '@/api/leave'

const router = useRouter()

function handleEnterProject(projectId) {
  if (!projectId) return
  router.push({ path: '/translation', query: { projectId } })
}

const scheduleDate = ref('')
const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return days[new Date(scheduleDate.value).getDay()]
})

const shiftTableData = ref([])
const leaveRecords = ref([])

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

function formatDateTimeValue(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  const sec = String(date.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day}T${h}:${min}:${sec}`
}

async function loadLeaveRecords() {
  const now = new Date()
  const nextMonth = new Date(now)
  nextMonth.setMonth(nextMonth.getMonth() + 1)

  try {
    const res = await getLeaveRecords({
      start_date: formatDateTimeValue(now),
      end_date: formatDateTimeValue(nextMonth)
    })

    leaveRecords.value = (Array.isArray(res) ? res : []).filter(item => {
      const start = new Date(item?.start_date)
      return !isNaN(start.getTime()) && start >= now && start <= nextMonth
    })
  } catch {
    leaveRecords.value = []
  }
}

async function loadScheduleForDate(date) {
  try {
    const stored = await getSchedule(date)
    shiftTableData.value = stored.shift_table ?? []
  } catch {
    shiftTableData.value = []
  }
}

const currentUserName = ref('')
function initCurrentUserName() {
  try {
    currentUserName.value = (localStorage.getItem('user_name') || '').trim()
  } catch {
    currentUserName.value = ''
  }
}

const workflowTasks = ref([])
async function loadMyWorkflowTasks() {
  try {
    const tasks = await getMyTasksAPI()
    workflowTasks.value = Array.isArray(tasks) ? tasks : []
  } catch {
    workflowTasks.value = []
  }
}

function onDateChange() {
  loadScheduleForDate(scheduleDate.value)
}

onMounted(() => {
  initCurrentUserName()
  const today = new Date()
  scheduleDate.value = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, '0'),
    String(today.getDate()).padStart(2, '0')
  ].join('-')
  loadScheduleForDate(scheduleDate.value)
  loadMyWorkflowTasks()
  loadLeaveRecords()
})
</script>

<style scoped>
.dashboard-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.section-block {
  margin-bottom: 28px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-color-primary-light-7);
}

.info-block {
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.section-desc {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.data-table {
  margin-bottom: 12px;
}

.empty-tip {
  padding: 20px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
