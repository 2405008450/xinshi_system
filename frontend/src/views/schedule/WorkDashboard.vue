<template>
  <el-card class="workbench-card" shadow="never">
    <template #header>
      <ScheduleHeader
        title="工作台"
        :model-value="scheduleDate"
        :weekday-label="weekdayLabel"
        :show-admin-actions="false"
        :readonly="false"
        @update:model-value="scheduleDate = $event"
        @change="onDateChange"
      >
        <template #context>
          <MyShiftStatus :loading="shiftLoading" :day="myShiftDay" />
        </template>
      </ScheduleHeader>
    </template>

    <div class="dashboard-flow">
      <PendingHandoversPanel @updated="loadMyWorkItems" />

      <div class="overview-strip">
        <div class="stat-chip danger">
          <span class="stat-chip__label">逾期任务</span>
          <strong>{{ overdueTasks.length }}</strong>
          <small>超过预定完成时间</small>
        </div>
        <div class="stat-chip warning">
          <span class="stat-chip__label">即将到期</span>
          <strong>{{ urgentTasks.length }}</strong>
          <small>24 小时内</small>
        </div>
        <div class="stat-chip info">
          <span class="stat-chip__label">项目待办</span>
          <strong>{{ projectPendingCount }}</strong>
          <small>直接负责与角色池任务</small>
        </div>
        <div class="stat-chip neutral">
          <span class="stat-chip__label">我的待办</span>
          <strong>{{ pendingWorkItemCount }}</strong>
          <small>项目与非项目任务</small>
        </div>
        <el-badge
          :value="onLeaveCount"
          :hidden="!onLeaveCount"
          type="danger"
          class="shift-badge"
        >
          <el-button class="shift-matrix-btn" @click="matrixVisible = true">
            班次矩阵
            <span class="shift-matrix-btn__hint">部门排班 / 公司请假</span>
          </el-button>
        </el-badge>
      </div>

      <CollapsibleSection
        title="我的任务"
        subtitle="管理项目与执行任务"
        storage-key="my-tasks"
      >
        <ProjectManagerHandoverPanel v-if="canManageProjectOwnership" />
        <div v-if="canManageProjectOwnership" class="task-subsection-title">执行任务与交接</div>
        <UnifiedTasksPanel
          :current-user-name="currentUserName"
          :items="workItems"
          :reference-date="scheduleDate"
          @open-chat="handleOpenProjectChat"
          @refresh="loadMyWorkItems"
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="个人工作日报"
        subtitle="汇总、补充、确认并导出当日工作"
        storage-key="daily-report"
        :default-open="false"
      >
        <DailyReportPanel :report-date="scheduleDate" />
      </CollapsibleSection>
    </div>

    <ShiftMatrixDialog
      v-model="matrixVisible"
      :reference-date="scheduleDate"
      :on-leave-count="onLeaveCount"
    />
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ScheduleHeader from './components/ScheduleHeader.vue'
import UnifiedTasksPanel from './components/UnifiedTasksPanel.vue'
import DailyReportPanel from './components/DailyReportPanel.vue'
import ShiftMatrixDialog from './components/ShiftMatrixDialog.vue'
import MyShiftStatus from './components/MyShiftStatus.vue'
import PendingHandoversPanel from './components/PendingHandoversPanel.vue'
import ProjectManagerHandoverPanel from './components/ProjectManagerHandoverPanel.vue'
import CollapsibleSection from './components/CollapsibleSection.vue'
import { getMyWorkItems } from '@/api/tasks'
import { getOnLeaveUsers } from '@/api/leave'
import { getMyEmployeeShift } from '@/api/schedule'
import { hasRole, isSuperAdmin } from '@/utils/permission'
import { DEADLINE_STATE, getWorkItemDeadlineState, isWorkItemOpen } from '@/utils/workItemDeadline'

const router = useRouter()
const scheduleDate = ref('')
const dayLeaveRecords = ref([])
const workItems = ref([])
const currentUserName = ref('')
const matrixVisible = ref(false)
const canManageProjectOwnership = computed(() => hasRole('项目经理') || isSuperAdmin())
const currentUserId = (() => {
  try {
    return String(localStorage.getItem('user_id') || '')
  } catch {
    return ''
  }
})()

const myShift = ref(null)
const shiftLoading = ref(false)
let shiftRequestId = 0
let shiftController = null
let dayLeaveRequestId = 0
let dayLeaveController = null

const myShiftDay = computed(() => myShift.value?.days?.[0] || null)
const onLeaveCount = computed(() => dayLeaveRecords.value.length)

const personalOpenWorkItems = computed(() => workItems.value.filter(item => {
  if (!isWorkItemOpen(item)) return false
  return item.source_type !== 'non_project' || String(item.assignee_id || '') === currentUserId
}))
const projectPendingCount = computed(() => personalOpenWorkItems.value.filter(item => item.source_type === 'project').length)
const pendingWorkItemCount = computed(() => personalOpenWorkItems.value.length)

const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return new Date(scheduleDate.value).toLocaleDateString('zh-CN', { weekday: 'long' })
})

function handleOpenProjectChat(projectId) {
  if (!projectId) return
  router.push({ path: '/translation', query: { projectId, tab: 'chat' } })
}

function getReferenceDate() {
  if (scheduleDate.value) {
    const date = new Date(`${scheduleDate.value}T00:00:00`)
    if (!Number.isNaN(date.getTime())) return date
  }
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

const overdueTasks = computed(() => personalOpenWorkItems.value.filter(
  item => getWorkItemDeadlineState(item) === DEADLINE_STATE.OVERDUE
))
const urgentTasks = computed(() => personalOpenWorkItems.value.filter(
  item => getWorkItemDeadlineState(item) === DEADLINE_STATE.URGENT
))

async function loadDayLeaveRecords(targetDate) {
  if (!targetDate) return
  const requestId = ++dayLeaveRequestId
  if (dayLeaveController) {
    try { dayLeaveController.abort() } catch {}
  }
  dayLeaveController = typeof AbortController !== 'undefined' ? new AbortController() : null
  try {
    const res = await getOnLeaveUsers(targetDate, dayLeaveController?.signal)
    if (requestId !== dayLeaveRequestId) return
    dayLeaveRecords.value = Array.isArray(res) ? res : []
  } catch (err) {
    if (requestId !== dayLeaveRequestId) return
    if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
    dayLeaveRecords.value = []
  }
}

async function loadMyShift(targetDate) {
  if (!targetDate) return
  const requestId = ++shiftRequestId
  if (shiftController) {
    try { shiftController.abort() } catch {}
  }
  shiftController = typeof AbortController !== 'undefined' ? new AbortController() : null
  shiftLoading.value = true
  try {
    const data = await getMyEmployeeShift(targetDate, false, shiftController?.signal)
    if (requestId !== shiftRequestId) return
    myShift.value = data.me || null
  } catch (err) {
    if (requestId !== shiftRequestId) return
    if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
    myShift.value = null
  } finally {
    if (requestId === shiftRequestId) shiftLoading.value = false
  }
}

function initCurrentUserName() {
  try {
    currentUserName.value = (localStorage.getItem('user_name') || '').trim()
  } catch {
    currentUserName.value = ''
  }
}

async function loadMyWorkItems() {
  try {
    const tasks = await getMyWorkItems()
    workItems.value = Array.isArray(tasks) ? tasks : []
  } catch {
    workItems.value = []
  }
}

function onDateChange() {}

watch(() => scheduleDate.value, (value) => {
  if (!value) return
  loadMyShift(value)
  loadDayLeaveRecords(value)
})

onBeforeUnmount(() => {
  if (shiftController) {
    try { shiftController.abort() } catch {}
  }
  if (dayLeaveController) {
    try { dayLeaveController.abort() } catch {}
  }
})

onMounted(() => {
  initCurrentUserName()
  const today = getReferenceDate()
  scheduleDate.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  loadMyWorkItems()
})
</script>

<style scoped>
.workbench-card {
  border-color: var(--el-border-color-lighter);
}

.workbench-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.workbench-card :deep(.el-card__body) {
  padding: 12px;
}

.dashboard-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.overview-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 8px;
  margin-bottom: 8px;
}

.stat-chip {
  flex: 1 1 130px;
  min-width: 130px;
  min-height: 54px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light);
  background: #fff;
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  column-gap: 10px;
  align-items: center;
}

.stat-chip strong {
  grid-column: 2;
  grid-row: 1 / 3;
  font-size: 22px;
  line-height: 1;
}

.stat-chip small {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-chip.danger { border-left: 3px solid var(--el-color-danger); }
.stat-chip.warning { border-left: 3px solid var(--el-color-warning); }
.stat-chip.info { border-left: 3px solid var(--el-color-primary); }
.stat-chip.neutral { border-left: 3px solid var(--el-color-info); }

.stat-chip__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.shift-badge {
  flex: none;
  align-self: center;
  margin-left: auto;
}

.shift-matrix-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  height: auto;
  padding: 6px 16px;
  line-height: 1.2;
}

.shift-matrix-btn__hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.section-desc {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.data-table {
  margin-bottom: 12px;
}

.workbench-card :deep(.workbench-data-table .el-table__header th.el-table__cell) {
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.workbench-card :deep(.workbench-data-table td.el-table__cell) {
  padding: 6px 0;
}

.workbench-card :deep(.workbench-project-cell) {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.workbench-card :deep(.workbench-project-cell__title) {
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-card :deep(.workbench-project-cell__meta) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.35;
}

.empty-tip {
  padding: 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.workbench-card :deep(.el-table__empty-block) {
  min-height: 48px;
}

.task-subsection-title {
  margin: 8px 0 4px;
  padding-top: 6px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.workbench-card :deep(.el-button:not(.is-circle):not(.is-link)) {
  min-height: 28px;
  padding: 5px 10px;
}

@media (max-width: 900px) {
  .shift-badge {
    margin-left: 0;
  }
}

@media (max-width: 720px) {
  .workbench-card :deep(.el-card__header),
  .workbench-card :deep(.el-card__body) {
    padding: 10px;
  }
}
</style>
