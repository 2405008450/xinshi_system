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
      <PendingHandoversPanel v-if="canOperateWorkflow" @updated="loadMyWorkItems" />

      <div class="overview-strip">
        <div class="stat-chip danger">
          <span class="stat-chip__label">逾期任务</span>
          <strong>{{ overdueTasks.length }}</strong>
        </div>
        <div class="stat-chip warning">
          <span class="stat-chip__label">即将到期</span>
          <strong>{{ urgentTasks.length }}</strong>
        </div>
        <div class="stat-chip info">
          <span class="stat-chip__label">项目待办</span>
          <strong>{{ projectPendingCount }}</strong>
        </div>
        <div class="stat-chip neutral">
          <span class="stat-chip__label">我的待办</span>
          <strong>{{ pendingWorkItemCount }}</strong>
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

      <el-tabs v-model="activeSection" type="border-card" class="workbench-tabs">
        <el-tab-pane name="tasks">
          <template #label>
            <span>我的任务<template v-if="pendingWorkItemCount">（{{ pendingWorkItemCount }}）</template></span>
          </template>
          <ProjectManagerHandoverPanel v-if="canManageProjectOwnership" @open-project="handleOpenProject" />
          <div v-if="canManageProjectOwnership" class="task-subsection-title">执行任务与交接</div>
          <UnifiedTasksPanel
            :current-user-name="currentUserName"
            :items="workItems"
            :reference-date="scheduleDate"
            @open-chat="handleOpenProjectChat"
            @open-project="handleOpenProject"
            @refresh="loadMyWorkItems"
          />
        </el-tab-pane>
        <el-tab-pane name="daily-report" lazy>
          <template #label>
            <span class="daily-report-tab-label">
              个人工作日报
              <el-tag
                v-if="dailyReportStatusTag"
                :type="dailyReportStatusTag.type"
                size="small"
                effect="plain"
                class="daily-report-tab-label__tag"
              >
                {{ dailyReportStatusTag.text }}
              </el-tag>
            </span>
          </template>
          <DailyReportPanel :report-date="scheduleDate" @status-change="onDailyReportStatus" />
        </el-tab-pane>
      </el-tabs>
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
import { getMyWorkItems } from '@/api/tasks'
import { getOnLeaveUsers } from '@/api/leave'
import { getMyEmployeeShift } from '@/api/schedule'
import { hasPermission, hasRole, isSuperAdmin } from '@/utils/permission'
import { DEADLINE_STATE, getWorkItemDeadlineState, isWorkItemOpen } from '@/utils/workItemDeadline'

const router = useRouter()
const scheduleDate = ref('')
const dayLeaveRecords = ref([])
const workItems = ref([])
const currentUserName = ref('')
const matrixVisible = ref(false)

const MAIN_TAB_STORAGE_KEY = 'workbench_main_tab'
const MAIN_TAB_NAMES = ['tasks', 'daily-report']

function readInitialMainTab() {
  try {
    const stored = localStorage.getItem(MAIN_TAB_STORAGE_KEY)
    if (stored && MAIN_TAB_NAMES.includes(stored)) return stored
  } catch {}
  return 'tasks'
}

const activeSection = ref(readInitialMainTab())
const dailyReportStatus = ref(null)
const canManageProjectOwnership = computed(() => hasRole('项目经理') || isSuperAdmin())
const canOperateWorkflow = computed(() => hasPermission(['projects:read', 'workflow:operate']))
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

const dailyReportStatusTag = computed(() => {
  const status = dailyReportStatus.value
  if (!status || status.date !== scheduleDate.value) return null
  return status.status === 'finalized'
    ? { text: '已确认', type: 'success' }
    : { text: '草稿', type: 'info' }
})

function onDailyReportStatus(payload) {
  dailyReportStatus.value = payload || null
}

watch(activeSection, (value) => {
  try {
    localStorage.setItem(MAIN_TAB_STORAGE_KEY, value)
  } catch {}
})

const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return new Date(scheduleDate.value).toLocaleDateString('zh-CN', { weekday: 'long' })
})

function handleOpenProjectChat(projectId) {
  if (!projectId) return
  router.push({ path: '/translation', query: { projectId, tab: 'chat' } })
}

function handleOpenProject(item) {
  const routeName = item?.detail_route_name || {
    translation: 'TranslationProjectDetails',
    interpretation: 'InterpretationProjectDetails',
    annotation: 'AnnotationProjectDetails',
    recruitment: 'RecruitmentProjectDetails'
  }[item?.project_type || 'translation']
  const projectId = item?.project_id || item?.translation_project_id
  if (!routeName || !projectId) return
  router.push({ name: routeName, query: { projectId } })
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
  border-color: #cbd5e1;
  background: #e9eef4;
}

.workbench-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom-color: #cbd5e1;
  background: var(--el-bg-color);
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
  flex: 1 1 100px;
  min-width: 100px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: #fff;
  box-shadow: 0 1px 2px rgb(15 23 42 / 8%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.stat-chip strong {
  font-size: 18px;
  line-height: 1;
}

.stat-chip.danger { border-left: 4px solid var(--el-color-danger); background: #fff8f8; }
.stat-chip.warning { border-left: 4px solid var(--el-color-warning); background: #fffbf2; }
.stat-chip.info { border-left: 4px solid var(--el-color-primary); background: #f5f9ff; }
.stat-chip.neutral { border-left: 4px solid #64748b; background: #f8fafc; }

.stat-chip__label {
  font-size: 12px;
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

/* Element Plus 会把按钮内容包一层 span，需在内层 span 上做两行布局 */
.shift-matrix-btn :deep(> span) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
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

.workbench-card :deep(.row-click-select-table .el-table__row) {
  cursor: pointer;
}

.workbench-card :deep(.workbench-project-cell) {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.workbench-card :deep(.workbench-project-cell__title) {
  overflow: hidden;
  color: #3f6173;
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
  padding: 7px 10px;
  border-left: 3px solid #475569;
  background: #eef2f6;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.workbench-tabs {
  margin-bottom: 8px;
  border: 1px solid #b8c3d1;
  border-radius: 8px;
  box-shadow: 0 2px 5px rgb(15 23 42 / 8%);
  overflow: hidden;
}

.workbench-tabs :deep(.el-tabs__header) {
  margin: 0;
  background: #475569;
  border-bottom: 0;
}

.workbench-tabs :deep(.el-tabs__item) {
  height: 38px;
  padding: 0 16px;
  color: #dbe4ee;
  font-size: 14px;
}

.workbench-tabs :deep(.el-tabs__item:hover) {
  color: #fff;
}

.workbench-tabs :deep(.el-tabs__item.is-active) {
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-weight: 600;
  border-right-color: #b8c3d1;
  border-left-color: #b8c3d1;
}

.workbench-tabs :deep(.el-tabs__content) {
  padding: 10px 12px 12px;
}

.daily-report-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.daily-report-tab-label__tag {
  flex: none;
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
