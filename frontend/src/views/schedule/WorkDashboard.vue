<template>
  <el-card>
    <template #header>
      <ScheduleHeader
        title="My Workbench"
        :model-value="scheduleDate"
        :weekday-label="weekdayLabel"
        :show-admin-actions="false"
        :readonly="false"
        @update:model-value="scheduleDate = $event"
        @change="onDateChange"
      />
    </template>

    <div class="dashboard-flow">
      <section class="section-block summary-grid">
        <div class="summary-card danger">
          <span class="summary-label">Overdue</span>
          <strong>{{ overdueTasks.length }}</strong>
          <small>tasks past deadline</small>
        </div>
        <div class="summary-card warning">
          <span class="summary-label">Due Soon</span>
          <strong>{{ urgentTasks.length }}</strong>
          <small>within 24 hours</small>
        </div>
        <div class="summary-card info">
          <span class="summary-label">My Tasks</span>
          <strong>{{ workflowTasks.length }}</strong>
          <small>current workflow items</small>
        </div>
        <div class="summary-card neutral">
          <span class="summary-label">Upcoming Leave</span>
          <strong>{{ leaveRecords.length }}</strong>
          <small>next 30 days</small>
        </div>
      </section>

      <section v-if="overdueTasks.length || urgentTasks.length" class="section-block">
        <el-alert
          :title="alertTitle"
          type="warning"
          :closable="false"
          show-icon
          class="deadline-alert"
        />
        <el-table :data="attentionTasks" border size="small" class="data-table" style="margin-top: 12px;">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="project_name" label="Project" min-width="220" show-overflow-tooltip />
          <el-table-column prop="order_no" label="Order No" width="180" />
          <el-table-column prop="client_short_name" label="Client" width="140" show-overflow-tooltip />
          <el-table-column label="Deadline" width="180">
            <template #default="{ row }">{{ formatDateTime(getTaskDeadline(row)) }}</template>
          </el-table-column>
          <el-table-column label="Status" width="100">
            <template #default="{ row }">
              <el-tag :type="isOverdue(row) ? 'danger' : 'warning'" size="small">{{ isOverdue(row) ? 'Overdue' : 'Due Soon' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Action" width="100" align="center">
            <template #default="{ row }">
              <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="handleEnterProject(row.translation_project_id)">Open</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="section-block">
        <h3 class="section-title">My Tasks</h3>
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
        <h4 class="section-title">Leave Overview</h4>
        <p class="section-desc">Read-only leave records for the next 30 days.</p>
        <el-table v-if="leaveRecords.length" :data="leaveRecords" border size="small" class="data-table">
          <el-table-column prop="employee_name" label="Employee" width="120" />
          <el-table-column label="Start" width="170">
            <template #default="{ row }">{{ formatDateTime(row.start_date) }}</template>
          </el-table-column>
          <el-table-column label="End" width="170">
            <template #default="{ row }">{{ formatDateTime(row.end_date) }}</template>
          </el-table-column>
          <el-table-column prop="leave_type" label="Type" width="120" />
          <el-table-column prop="reason" label="Reason" min-width="180" show-overflow-tooltip />
        </el-table>
        <div v-else class="empty-tip">No leave records in the next 30 days.</div>
      </section>
    </div>
  </el-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ScheduleHeader from './components/ScheduleHeader.vue'
import MyTasksPanel from './components/MyTasksPanel.vue'
import ShiftTableReadonly from './components/ShiftTableReadonly.vue'
import { getSchedule } from '@/api/schedule'
import { getMyTasksAPI } from '@/api/workflow'
import { getLeaveRecords } from '@/api/leave'

const router = useRouter()
const scheduleDate = ref('')
const shiftTableData = ref([])
const leaveRecords = ref([])
const workflowTasks = ref([])
const currentUserName = ref('')

const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return new Date(scheduleDate.value).toLocaleDateString('en-US', { weekday: 'long' })
})

const getTaskDeadline = (task) => task?.customer_deadline_time ?? task?.customerDeadlineTime ?? null

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDateTimeValue(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function handleEnterProject(projectId) {
  if (!projectId) return
  router.push({ path: '/translation', query: { projectId } })
}

function getReferenceDate() {
  if (scheduleDate.value) {
    const date = new Date(`${scheduleDate.value}T00:00:00`)
    if (!Number.isNaN(date.getTime())) return date
  }
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

function isOverdue(task) {
  const deadlineRaw = getTaskDeadline(task)
  if (!deadlineRaw) return false
  const deadline = new Date(deadlineRaw)
  if (Number.isNaN(deadline.getTime())) return false
  return deadline < new Date()
}

function isUrgent(task) {
  const deadlineRaw = getTaskDeadline(task)
  if (!deadlineRaw) return false
  const deadline = new Date(deadlineRaw)
  if (Number.isNaN(deadline.getTime())) return false
  const now = new Date()
  const next24Hours = new Date(now.getTime() + 24 * 60 * 60 * 1000)
  return deadline >= now && deadline <= next24Hours
}

const overdueTasks = computed(() => workflowTasks.value.filter(isOverdue))
const urgentTasks = computed(() => workflowTasks.value.filter(task => !isOverdue(task) && isUrgent(task)))
const attentionTasks = computed(() => [...overdueTasks.value, ...urgentTasks.value].slice(0, 8))
const alertTitle = computed(() => {
  if (overdueTasks.value.length && urgentTasks.value.length) {
    return `${overdueTasks.value.length} overdue task(s), ${urgentTasks.value.length} due soon.`
  }
  if (overdueTasks.value.length) {
    return `${overdueTasks.value.length} overdue task(s) need attention.`
  }
  return `${urgentTasks.value.length} task(s) due within 24 hours.`
})

async function loadLeaveRecords() {
  const now = new Date()
  const nextMonth = new Date(now)
  nextMonth.setMonth(nextMonth.getMonth() + 1)

  try {
    const res = await getLeaveRecords({
      start_date: formatDateTimeValue(now),
      end_date: formatDateTimeValue(nextMonth)
    })
    leaveRecords.value = Array.isArray(res) ? res : []
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

function initCurrentUserName() {
  try {
    currentUserName.value = (localStorage.getItem('user_name') || '').trim()
  } catch {
    currentUserName.value = ''
  }
}

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
  const today = getReferenceDate()
  scheduleDate.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 18px;
  border-radius: 12px;
  border: 1px solid var(--el-border-color-light);
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-card strong {
  font-size: 28px;
  line-height: 1;
}

.summary-card small {
  color: var(--el-text-color-secondary);
}

.summary-card.danger { border-top: 4px solid var(--el-color-danger); }
.summary-card.warning { border-top: 4px solid var(--el-color-warning); }
.summary-card.info { border-top: 4px solid var(--el-color-primary); }
.summary-card.neutral { border-top: 4px solid var(--el-color-info); }

.summary-label {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--el-text-color-secondary);
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

.deadline-alert {
  margin-bottom: 0;
}

.empty-tip {
  padding: 20px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
