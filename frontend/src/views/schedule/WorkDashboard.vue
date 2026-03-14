<template>
  <el-card>
    <template #header>
      <ScheduleHeader
        title="&#x6211;&#x7684;&#x5DE5;&#x4F5C;&#x53F0;"
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
          <span class="summary-label">&#x5DF2;&#x903E;&#x671F;</span>
          <strong>{{ overdueTasks.length }}</strong>
          <small>&#x5DF2;&#x8D85;&#x8FC7;&#x622A;&#x6B62;&#x65F6;&#x95F4;</small>
        </div>
        <div class="summary-card warning">
          <span class="summary-label">&#x5373;&#x5C06;&#x5230;&#x671F;</span>
          <strong>{{ urgentTasks.length }}</strong>
          <small>24 &#x5C0F;&#x65F6;&#x5185;&#x5230;&#x671F;</small>
        </div>
        <div class="summary-card info">
          <span class="summary-label">&#x6211;&#x7684;&#x4EFB;&#x52A1;</span>
          <strong>{{ workflowTasks.length }}</strong>
          <small>&#x5F53;&#x524D;&#x6D41;&#x7A0B;&#x4EFB;&#x52A1;</small>
        </div>
        <div class="summary-card neutral">
          <span class="summary-label">&#x5373;&#x5C06;&#x8BF7;&#x5047;</span>
          <strong>{{ leaveRecords.length }}</strong>
          <small>&#x672A;&#x6765; 30 &#x5929;</small>
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
          <el-table-column prop="project_name" label="&#x9879;&#x76EE;&#x540D;&#x79F0;" min-width="220" show-overflow-tooltip />
          <el-table-column prop="order_no" label="&#x8BA2;&#x5355;&#x53F7;" width="180" />
          <el-table-column prop="client_short_name" label="&#x5BA2;&#x6237;" width="140" show-overflow-tooltip />
          <el-table-column label="&#x622A;&#x6B62;&#x65F6;&#x95F4;" width="180">
            <template #default="{ row }">{{ formatDateTime(getTaskDeadline(row)) }}</template>
          </el-table-column>
          <el-table-column label="&#x72B6;&#x6001;" width="100">
            <template #default="{ row }">
              <el-tag :type="isOverdue(row) ? 'danger' : 'warning'" size="small">{{ isOverdue(row) ? '已逾期' : '即将到期' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="&#x64CD;&#x4F5C;" width="100" align="center">
            <template #default="{ row }">
              <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="handleEnterProject(row.translation_project_id)">&#x8FDB;&#x5165;</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="section-block">
        <h3 class="section-title">&#x6211;&#x7684;&#x4EFB;&#x52A1;</h3>
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
        <h4 class="section-title">&#x8BF7;&#x5047;&#x6982;&#x89C8;</h4>
        <p class="section-desc">&#x672A;&#x6765; 30 &#x5929;&#x8BF7;&#x5047;&#x8BB0;&#x5F55;&#xFF0C;&#x53EA;&#x8BFB;&#x5C55;&#x793A;&#x3002;</p>
        <el-table v-if="leaveRecords.length" :data="leaveRecords" border size="small" class="data-table">
          <el-table-column prop="employee_name" label="&#x5458;&#x5DE5;" width="120" />
          <el-table-column label="&#x5F00;&#x59CB;&#x65F6;&#x95F4;" width="170">
            <template #default="{ row }">{{ formatDateTime(row.start_date) }}</template>
          </el-table-column>
          <el-table-column label="&#x7ED3;&#x675F;&#x65F6;&#x95F4;" width="170">
            <template #default="{ row }">{{ formatDateTime(row.end_date) }}</template>
          </el-table-column>
          <el-table-column prop="leave_type" label="&#x8BF7;&#x5047;&#x7C7B;&#x578B;" width="120" />
          <el-table-column prop="reason" label="&#x539F;&#x56E0;" min-width="180" show-overflow-tooltip />
        </el-table>
        <div v-else class="empty-tip">&#x672A;&#x6765; 30 &#x5929;&#x6682;&#x65E0;&#x8BF7;&#x5047;&#x8BB0;&#x5F55;&#x3002;</div>
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
  return new Date(scheduleDate.value).toLocaleDateString('zh-CN', { weekday: 'long' })
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
    return `共有 ${overdueTasks.value.length} 项任务已逾期，${urgentTasks.value.length} 项任务即将到期。`
  }
  if (overdueTasks.value.length) {
    return `共有 ${overdueTasks.value.length} 项逾期任务需要处理。`
  }
  return `共有 ${urgentTasks.value.length} 项任务将在 24 小时内到期。`
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
