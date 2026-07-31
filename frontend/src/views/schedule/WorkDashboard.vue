<template>
  <el-card>
    <template #header>
      <ScheduleHeader
        title="工作台"
        :model-value="scheduleDate"
        :weekday-label="weekdayLabel"
        :show-admin-actions="false"
        :readonly="false"
        @update:model-value="scheduleDate = $event"
        @change="onDateChange"
      />
    </template>

    <div class="dashboard-flow">
      <PendingHandoversPanel @updated="loadMyWorkItems" />

      <CollapsibleSection
        title="工作概览"
        subtitle="项目风险、进行中项目与个人待办"
        storage-key="summary"
      >
        <div class="summary-grid">
          <div class="summary-card danger">
            <span class="summary-label">项目逾期</span>
            <strong>{{ activeProjectSummary.overdue }}</strong>
            <small>超过交稿时间</small>
          </div>
          <div class="summary-card warning">
            <span class="summary-label">即将到期</span>
            <strong>{{ activeProjectSummary.dueSoon }}</strong>
            <small>24 小时内</small>
          </div>
          <div class="summary-card info">
            <span class="summary-label">进行中项目</span>
            <strong>{{ activeProjectSummary.total }}</strong>
            <small>母订单与子订单</small>
          </div>
          <div class="summary-card neutral">
            <span class="summary-label">我的待办</span>
            <strong>{{ pendingWorkItemCount }}</strong>
            <small>项目与非项目任务</small>
          </div>
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        v-if="overdueTasks.length || urgentTasks.length"
        title="到期提醒"
        subtitle="需要优先处理的个人任务"
        storage-key="deadline-alerts"
      >
        <template #badge>
          <el-tag type="warning" size="small">{{ overdueTasks.length + urgentTasks.length }}</el-tag>
        </template>
        <el-alert
          :title="alertTitle"
          type="warning"
          :closable="false"
          show-icon
          class="deadline-alert"
        />
        <el-table :data="attentionTasks" border size="small" class="data-table" style="margin-top: 12px;">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="task_name" label="任务名称" min-width="220" show-overflow-tooltip />
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
      </CollapsibleSection>

      <CollapsibleSection
        v-if="canReadProjects"
        title="进行中项目"
        subtitle="尚未完成、取消或终止的母订单与子订单"
        storage-key="active-projects"
      >
        <div class="section-heading">
          <div class="active-project-toolbar">
            <el-input
              v-model="activeProjectKeyword"
              clearable
              placeholder="搜索订单、项目、客户或负责人"
              style="width: 280px"
              @keyup.enter="searchActiveProjects"
              @clear="searchActiveProjects"
            />
            <el-button type="primary" :loading="activeProjectsLoading" @click="searchActiveProjects">查询</el-button>
            <el-button @click="goToProjectDetails">查看全部项目详情</el-button>
          </div>
        </div>
        <el-table
          v-loading="activeProjectsLoading"
          :data="activeProjects"
          border
          size="small"
          class="data-table"
        >
          <el-table-column label="类型" width="82">
            <template #default="{ row }">
              <el-tag :type="row.entity_type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
                {{ row.entity_type === 'suborder' ? '子订单' : '母订单' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="order_no" label="订单号" width="180" show-overflow-tooltip />
          <el-table-column label="项目名称" min-width="210" show-overflow-tooltip>
            <template #default="{ row }">{{ row.sub_project_name || row.project_name }}</template>
          </el-table-column>
          <el-table-column prop="client_short_name" label="客户" width="120" show-overflow-tooltip />
          <el-table-column label="当前环节" width="120">
            <template #default="{ row }">{{ stageLabel(row.current_stage_key) }}</template>
          </el-table-column>
          <el-table-column label="当前处理人" width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.current_assignee_name || row.group_assign_role || '待分配' }}</template>
          </el-table-column>
          <el-table-column label="项目经理" width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.project_manager_name || '未绑定' }}</template>
          </el-table-column>
          <el-table-column label="客户交稿时间" width="165">
            <template #default="{ row }">{{ formatDateTime(row.customer_deadline_time) }}</template>
          </el-table-column>
          <el-table-column label="风险" width="100">
            <template #default="{ row }">
              <el-tag v-if="isOverdue(row)" type="danger" size="small">已逾期</el-tag>
              <el-tag v-else-if="isUrgent(row)" type="warning" size="small">即将到期</el-tag>
              <el-tag v-else type="success" size="small" effect="plain">正常</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="handleEnterProject(row)">进入</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="active-project-pagination">
          <el-pagination
            v-model:current-page="activeProjectPagination.page"
            v-model:page-size="activeProjectPagination.pageSize"
            :total="activeProjectSummary.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadActiveProjects"
            @current-change="loadActiveProjects"
          />
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title="今日班次"
        subtitle="当日各岗位排班信息"
        storage-key="today-shifts"
        :default-open="false"
      >
        <ShiftTableReadonly :data="shiftTableData" />
      </CollapsibleSection>

      <CollapsibleSection
        title="我的任务"
        subtitle="执行任务交接与管理层项目归属交接分开处理"
        storage-key="my-tasks"
      >
        <ProjectManagerHandoverPanel
          v-if="canManageProjectOwnership"
          @updated="loadActiveProjects"
        />
        <el-divider v-if="canManageProjectOwnership" content-position="left">执行层任务与交接</el-divider>
        <UnifiedTasksPanel
          :current-user-name="currentUserName"
          :items="workItems"
          :reference-date="scheduleDate"
          @enter-project="handleEnterProject"
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

      <CollapsibleSection
        title="请假概览"
        subtitle="未来 30 天请假记录"
        storage-key="leave-overview"
        :default-open="false"
      >
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
      </CollapsibleSection>
    </div>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import ScheduleHeader from './components/ScheduleHeader.vue'
import UnifiedTasksPanel from './components/UnifiedTasksPanel.vue'
import DailyReportPanel from './components/DailyReportPanel.vue'
import ShiftTableReadonly from './components/ShiftTableReadonly.vue'
import PendingHandoversPanel from './components/PendingHandoversPanel.vue'
import ProjectManagerHandoverPanel from './components/ProjectManagerHandoverPanel.vue'
import CollapsibleSection from './components/CollapsibleSection.vue'
import { getSchedule } from '@/api/schedule'
import { getMyWorkItems } from '@/api/tasks'
import { getLeaveRecords } from '@/api/leave'
import { getActiveProjectsAPI } from '@/api/workflow'
import { hasPermission, hasRole, isSuperAdmin } from '@/utils/permission'

const router = useRouter()
const scheduleDate = ref('')
const shiftTableData = ref([])
const leaveRecords = ref([])
const workItems = ref([])
const currentUserName = ref('')
const activeProjects = ref([])
const activeProjectsLoading = ref(false)
const activeProjectKeyword = ref('')
const activeProjectPagination = reactive({ page: 1, pageSize: 20 })
const activeProjectSummary = reactive({ total: 0, overdue: 0, dueSoon: 0 })
const canReadProjects = computed(() => hasPermission('projects:read'))
const canManageProjectOwnership = computed(() => hasRole('项目经理') || isSuperAdmin())
const currentUserId = (() => {
  try {
    return String(localStorage.getItem('user_id') || '')
  } catch {
    return ''
  }
})()
const pendingWorkItemCount = computed(() => workItems.value.filter(item => {
  if (item.source_type === 'project') return true
  return ['pending', 'in_progress'].includes(item.status)
    && String(item.assignee_id || '') === currentUserId
}).length)
const STAGE_LABELS = {
  reception: '客户专员',
  layout_assign: '排版指派',
  project_manager: '项目经理',
  project_specialist: '项目专员',
  project_assistant: '项目助理',
  review: '译审',
  special_qc: '专检',
  layout: '排版'
}

const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return new Date(scheduleDate.value).toLocaleDateString('zh-CN', { weekday: 'long' })
})

const getTaskDeadline = (task) => task?.planned_completion_at ?? task?.customer_deadline_time ?? task?.customerDeadlineTime ?? null

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDateTimeValue(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function handleEnterProject(projectOrId) {
  const row = projectOrId && typeof projectOrId === 'object' ? projectOrId : null
  const projectId = row?.translation_project_id || projectOrId
  if (!projectId) return
  const query = { projectId, tab: 'overview' }
  if (row?.entity_type === 'suborder' && row.sub_order_id) {
    query.subOrderId = row.sub_order_id
  }
  router.push({ path: '/translation', query })
}

function handleOpenProjectChat(projectId) {
  if (!projectId) return
  router.push({ path: '/translation', query: { projectId, tab: 'chat' } })
}

function goToProjectDetails() {
  router.push('/translation-details')
}

function stageLabel(stage) {
  return STAGE_LABELS[stage] || stage || '-'
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
  if (task.source_type === 'non_project' && !['pending', 'in_progress'].includes(task.status)) {
    return false
  }
  const deadlineRaw = getTaskDeadline(task)
  if (!deadlineRaw) return false
  const deadline = new Date(deadlineRaw)
  if (Number.isNaN(deadline.getTime())) return false
  return deadline < new Date()
}

function isUrgent(task) {
  if (task.source_type === 'non_project' && !['pending', 'in_progress'].includes(task.status)) {
    return false
  }
  const deadlineRaw = getTaskDeadline(task)
  if (!deadlineRaw) return false
  const deadline = new Date(deadlineRaw)
  if (Number.isNaN(deadline.getTime())) return false
  const now = new Date()
  const next24Hours = new Date(now.getTime() + 24 * 60 * 60 * 1000)
  return deadline >= now && deadline <= next24Hours
}

const overdueTasks = computed(() => workItems.value.filter(isOverdue))
const urgentTasks = computed(() => workItems.value.filter(task => !isOverdue(task) && isUrgent(task)))
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

async function loadMyWorkItems() {
  try {
    const tasks = await getMyWorkItems()
    workItems.value = Array.isArray(tasks) ? tasks : []
  } catch {
    workItems.value = []
  }
}

async function loadActiveProjects() {
  if (!canReadProjects.value) return
  activeProjectsLoading.value = true
  try {
    const response = await getActiveProjectsAPI({
      skip: (activeProjectPagination.page - 1) * activeProjectPagination.pageSize,
      limit: activeProjectPagination.pageSize,
      keyword: activeProjectKeyword.value.trim() || undefined
    })
    activeProjects.value = Array.isArray(response?.items) ? response.items : []
    activeProjectSummary.total = response?.total || 0
    activeProjectSummary.overdue = response?.overdue_total || 0
    activeProjectSummary.dueSoon = response?.due_soon_total || 0
  } catch {
    activeProjects.value = []
    activeProjectSummary.total = 0
    activeProjectSummary.overdue = 0
    activeProjectSummary.dueSoon = 0
  } finally {
    activeProjectsLoading.value = false
  }
}

function searchActiveProjects() {
  activeProjectPagination.page = 1
  loadActiveProjects()
}

function onDateChange() {
  loadScheduleForDate(scheduleDate.value)
}

onMounted(() => {
  initCurrentUserName()
  const today = getReferenceDate()
  scheduleDate.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  loadScheduleForDate(scheduleDate.value)
  loadMyWorkItems()
  loadActiveProjects()
  loadLeaveRecords()
})
</script>

<style scoped>
.dashboard-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(130px, 1fr));
  gap: 8px;
}

.summary-card {
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

.summary-card strong {
  grid-column: 2;
  grid-row: 1 / 3;
  font-size: 22px;
  line-height: 1;
}

.summary-card small {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.summary-card.danger { border-left: 3px solid var(--el-color-danger); }
.summary-card.warning { border-left: 3px solid var(--el-color-warning); }
.summary-card.info { border-left: 3px solid var(--el-color-primary); }
.summary-card.neutral { border-left: 3px solid var(--el-color-info); }

.summary-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.section-heading,
.active-project-toolbar {
  display: flex;
  align-items: center;
}

.section-heading {
  justify-content: flex-end;
  gap: 16px;
  margin-bottom: 12px;
}

.active-project-toolbar {
  gap: 8px;
}

.active-project-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
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

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(130px, 1fr));
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
