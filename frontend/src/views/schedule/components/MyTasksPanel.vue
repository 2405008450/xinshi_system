<template>
  <div class="section-block">
    <div class="task-toolbar">
      <div class="task-toolbar__actions">
        <el-button size="small" :type="showDelegatedOnly ? 'primary' : 'default'" plain @click="toggleDelegatedScope">
          我委托的任务（{{ delegatedOutTasks.length }}）
        </el-button>
        <el-button size="small" plain @click="toggleTaskScope">
          {{ showAllTasks ? '只看我的任务' : `显示全部任务（${hiddenOverviewTaskCount}）` }}
        </el-button>
        <el-button
          v-if="canOperateWorkflow"
          type="primary"
          size="small"
          :disabled="!directSelectedTasks.length"
          @click="openHandoverDialog"
        >
          交接所选任务（{{ directSelectedTasks.length }}）
        </el-button>
        <el-button
          v-if="canOperateWorkflow"
          type="success"
          plain
          size="small"
          :loading="claimingRolePool"
          :disabled="!rolePoolSelectedTasks.length"
          @click="claimSelectedRolePoolTasks"
        >认领任务（{{ rolePoolSelectedTasks.length }}）</el-button>
        <el-button v-if="canOperateWorkflow" type="warning" plain size="small" @click="openClaimDialog">继承他人任务</el-button>
      </div>
    </div>

    <el-table
      ref="taskTableRef"
      v-if="tasksList.length"
      :data="pagedTasks"
      border
      size="small"
      class="data-table workbench-data-table row-click-select-table"
      :row-class-name="rowClassName"
      @selection-change="selectedTasks = $event"
      @row-click="toggleTaskRowSelection"
    >
      <template #empty>
        <span class="table-filter-empty">没有符合当前筛选条件的任务，可调整列头筛选条件</span>
      </template>
      <el-table-column type="selection" :width="WORKBENCH_COLUMN_WIDTHS.selection" :selectable="isTaskSelectable" />
      <el-table-column type="index" label="序号" :width="WORKBENCH_COLUMN_WIDTHS.index" />
      <el-table-column prop="order_no" label="订单号" :width="WORKBENCH_COLUMN_WIDTHS.orderNo" show-overflow-tooltip />
      <el-table-column label="项目 / 任务" :width="WORKBENCH_COLUMN_WIDTHS.projectTask">
        <template #header>
          <ColumnHeaderFilter
            label="项目 / 任务"
            :active="projectFilterActive"
            :width="260"
            @clear="clearProjectFilters"
          >
            <div>
              <div class="column-header-filter__group-label">项目类型</div>
              <el-checkbox-group v-model="searchForm.project_types" class="project-type-filter-group">
                <el-checkbox
                  v-for="option in PROJECT_TYPE_OPTIONS"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
            <div>
              <div class="column-header-filter__group-label">关键词</div>
              <el-input
                v-model="searchForm.project"
                placeholder="项目、子项目或订单号"
                clearable
                size="small"
                @change="normalizeProjectSearch"
              />
            </div>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <div class="workbench-project-cell">
            <span
              class="workbench-project-cell__title"
              :title="row.entity_type === 'suborder' ? (row.sub_project_name || row.project_name || '-') : (row.project_name || '-')"
            >
              {{ row.entity_type === 'suborder' ? (row.sub_project_name || row.project_name || '-') : (row.project_name || '-') }}
            </span>
            <div class="workbench-project-cell__meta">
              <el-tag type="info" size="small" effect="plain">{{ row.project_type_label || '笔译项目' }}</el-tag>
              <el-tag :type="row.entity_type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
                {{ row.entity_type === 'suborder' ? '子订单' : '母项目' }}
              </el-tag>
              <span>{{ row.task_type || '项目任务' }}</span>
              <span v-if="row.entity_type === 'suborder' && row.project_name">母项目：{{ row.project_name }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="客户" :width="WORKBENCH_COLUMN_WIDTHS.client" show-overflow-tooltip>
        <template #header>
          <ColumnHeaderFilter
            label="客户"
            :active="!!searchForm.client"
            :width="220"
            @clear="searchForm.client = ''"
          >
            <el-input
              v-model="searchForm.client"
              placeholder="按客户简称筛选"
              clearable
              size="small"
            />
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">{{ row.client_short_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="计划节点" :width="WORKBENCH_COLUMN_WIDTHS.customerDeadline">
        <template #default="{ row }">
          <DeadlineHintCell :deadline="getTaskDeadline(row)" :status="row.project_status" />
        </template>
      </el-table-column>
      <el-table-column prop="project_status" label="项目状态" :width="WORKBENCH_COLUMN_WIDTHS.projectStatus">
        <template #header>
          <ColumnHeaderFilter
            label="项目状态"
            :active="!!searchForm.project_statuses.length"
            :width="260"
            @clear="searchForm.project_statuses = []"
          >
            <el-checkbox-group v-model="searchForm.project_statuses" class="project-status-filter-group">
              <el-checkbox
                v-for="option in projectStatusFilterOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}（{{ option.count }}）
              </el-checkbox>
            </el-checkbox-group>
            <div v-if="!projectStatusFilterOptions.length" class="column-filter-empty">暂无可筛选状态</div>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <ProjectStatusSwitch
            :project-type="resolveProjectType(row)"
            :project-id="resolveProjectId(row)"
            :status="row.project_status"
            :writable="canWriteProjects"
            @updated="handleProjectStatusUpdated(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="current_stage_role_name" label="所属角色" :width="WORKBENCH_COLUMN_WIDTHS.currentRole" show-overflow-tooltip>
        <template #default="{ row }">{{ row.current_stage_role_name || formatStage(row.current_stage_role_code) }}</template>
      </el-table-column>
      <el-table-column prop="language_pair" label="语言方向" :width="WORKBENCH_COLUMN_WIDTHS.languagePair">
        <template #header>
          <ColumnHeaderFilter
            label="语言方向"
            :active="!!searchForm.language_pair"
            :width="220"
            @clear="searchForm.language_pair = ''"
          >
            <el-input
              v-model="searchForm.language_pair"
              placeholder="按翻译方向筛选"
              clearable
              size="small"
            />
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <LanguagePairText :value="row.language_pair" />
        </template>
      </el-table-column>
      <el-table-column prop="difficulty" label="难度" :width="WORKBENCH_COLUMN_WIDTHS.difficulty">
        <template #default="{ row }">
          <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
            {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="current_assignee_name" label="当前负责人" :width="WORKBENCH_COLUMN_WIDTHS.currentAssignee">
        <template #header>
          <ColumnHeaderFilter
            label="当前负责人"
            :active="!!searchForm.assignees.length"
            :width="240"
            @clear="searchForm.assignees = []"
          >
            <el-checkbox-group v-model="searchForm.assignees" class="assignee-filter-group">
              <el-checkbox
                v-for="option in assigneeFilterOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}（{{ option.count }}）
              </el-checkbox>
            </el-checkbox-group>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <div class="assignee-cell">
            <ProjectRoleAssigneesPopover
              :current-assignee-name="row.current_assignee_name || ''"
              :current-stage-role-code="row.current_stage_role_code || ''"
              :current-stage-role-name="row.current_stage_role_name || ''"
              :group-assign-role="row.group_assign_role || ''"
              :role-assignments="row.role_assignments || []"
            />
            <el-tag v-if="row.transfer_mode === 'delegation'" :type="row.delegation_overdue ? 'danger' : 'primary'" size="small" effect="plain">
              代 {{ row.original_assignee_name || '原负责人' }} 处理{{ row.delegation_overdue ? ' · 已到期' : '' }}
            </el-tag>
            <span
              v-else-if="row.transfer_mode === 'permanent' && row.original_assignee_name"
              class="previous-assignee"
              :title="`前负责人：${row.original_assignee_name}`"
            >
              前 {{ row.original_assignee_name }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="分配" width="84">
        <template #default="{ row }">
          <el-tag :type="assignmentTagType(row)" size="small" effect="plain">
            {{ assignmentLabel(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="stageColumnEnabled" prop="current_stage_key" label="流程阶段（待启用）" width="145">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ formatStage(row.current_stage_key) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" align="center" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="$emit('open-project', row)">进入项目</el-button>
          <el-button
            v-if="projectMessageEnabled && row.translation_project_id"
            type="primary"
            link
            size="small"
            @click="$emit('open-chat', row.translation_project_id)"
          >
            留言
          </el-button>
          <el-button v-if="row.assignment_type === 'direct'" type="success" link size="small" @click="$emit('record-work', row)">记进展</el-button>
          <el-button v-if="hasAction(row, 'return_delegation')" type="warning" link size="small" @click="returnDelegation(row)">归还任务</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="filteredTasks.length" class="task-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="PAGE_SIZE"
        :total="filteredTasks.length"
        layout="total, prev, pager, next"
        small
        background
        @current-change="handlePageChange"
      />
    </div>
    <template v-if="!tasksList.length">
      <div v-if="currentUserName" class="empty-tip">暂无待处理任务或可认领的角色池任务。</div>
      <el-empty v-else description="请先登录，登录账号将用于匹配「我的任务」" />
    </template>

    <el-dialog v-model="handoverVisible" title="交接所选任务" width="720px" destroy-on-close>
      <el-alert
        :title="handoverTransferMode === 'delegation'
          ? `将 ${directSelectedTasks.length} 项${handoverRoleName || ''}任务临时委托给相同角色的其他负责人，接收人确认后生效。`
          : `将 ${directSelectedTasks.length} 项${handoverRoleName || ''}任务永久转交给相同角色的其他负责人，接收人确认后生效。`"
        type="warning"
        :closable="false"
        show-icon
        class="dialog-alert"
      />
      <el-form label-width="92px">
        <el-form-item label="责任方式" required>
          <el-radio-group v-model="handoverTransferMode">
            <el-radio label="permanent">永久转交</el-radio>
            <el-radio label="delegation">临时代办</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="handoverTransferMode === 'delegation'" label="计划结束" required>
          <div class="delegation-end-field">
            <el-date-picker
              v-model="delegationEndAt"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              placeholder="请选择计划结束时间"
              style="width: 100%"
            />
            <span>到期仅提醒，不会自动归还。</span>
          </div>
        </el-form-item>
        <el-form-item label="交接类型" required>
          <div class="handover-type-field">
            <el-radio-group v-model="handoverType">
              <el-radio label="daily_shift">每日班次交接</el-radio>
              <el-radio label="weekend_holiday">周末/节假日交接</el-radio>
              <el-radio label="leave_time_off">请假调休交接</el-radio>
              <el-radio label="other">其他</el-radio>
            </el-radio-group>
            <el-input
              v-if="handoverType === 'other'"
              v-model="handoverReasonDetail"
              maxlength="500"
              show-word-limit
              placeholder="请填写具体交接原因"
            />
          </div>
        </el-form-item>
        <el-form-item label="接收人" required>
          <el-select v-model="handoverTargetUserId" filterable placeholder="请选择可承接全部所选任务的用户" style="width: 100%">
            <el-option
              v-for="user in eligibleUsers"
              :key="user.id"
              :label="user.is_on_leave ? `${user.full_name || user.username}（${user.assignment_disabled_reason || '请假中'}）` : (user.full_name || user.username)"
              :value="user.id"
              :disabled="String(user.id) === currentUserId || user.is_on_leave"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="交接留言">
          <TransferNoteEditor v-model="handoverNote" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handoverVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingHandover" :disabled="!canSubmitHandover" @click="submitHandover">
          发起交接
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="claimVisible" title="继承他人任务" width="1080px" destroy-on-close>
      <el-alert
        title="仅展示你具备当前阶段角色、且由其他用户直接负责的未完成任务；继承无需原负责人审批。"
        type="info"
        :closable="false"
        show-icon
        class="dialog-alert"
      />
      <el-form :inline="true" class="claim-search">
        <el-form-item label="原负责人">
          <el-select v-model="claimFilters.ownerUserId" clearable filterable placeholder="全部" style="width: 180px" @change="loadTransferableTasks">
            <el-option v-for="owner in claimOwnerOptions" :key="owner.id" :label="owner.name" :value="owner.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="claimFilters.keyword"
            clearable
            placeholder="客户、项目或订单号"
            style="width: 240px"
            @input="onClaimKeywordInput"
            @keyup.enter="runClaimSearch"
            @clear="runClaimSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="claimLoading" @click="runClaimSearch">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table
        v-loading="claimLoading"
        :data="transferableTasks"
        border
        size="small"
        max-height="360"
        @selection-change="claimSelectedTasks = $event"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="current_assignee_name" label="原负责人" width="120" />
        <el-table-column prop="client_name" label="客户" min-width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="母项目" min-width="180" show-overflow-tooltip />
        <el-table-column prop="sub_project_name" label="子项目" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.sub_project_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="order_no" label="订单编号" width="165" />
        <el-table-column label="流程阶段（待启用）" width="145">
          <template #default="{ row }">{{ formatStage(row.current_stage_key) }}</template>
        </el-table-column>
      </el-table>
      <div class="claim-note">
        <div class="claim-note__label">继承留言（已选择 {{ claimSelectedTasks.length }} 项）</div>
        <TransferNoteEditor v-model="claimNote" />
      </div>
      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="warning" :loading="submittingClaim" :disabled="!claimSelectedTasks.length" @click="submitClaim">
          确认继承
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TransferNoteEditor from '@/components/TransferNoteEditor.vue'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import ProjectStatusSwitch from '@/components/common/ProjectStatusSwitch.vue'
import LanguagePairText from '@/components/common/LanguagePairText.vue'
import ColumnHeaderFilter from '@/components/common/ColumnHeaderFilter.vue'
import { WORKBENCH_COLUMN_WIDTHS } from '@/constants/workbenchColumns'
import { hasPermission } from '@/utils/permission'
import {
  getProjectStatusLabel,
  normalizeProjectStatus,
  resolveProjectId,
  resolveProjectType
} from '@/utils/projectStatus'
import ProjectRoleAssigneesPopover from './ProjectRoleAssigneesPopover.vue'
import {
  DEADLINE_STATE,
  compareWorkItemsByDeadline,
  getWorkItemDeadline,
  getWorkItemDeadlineState
} from '@/utils/workItemDeadline'
import {
  claimWorkflowTasksAPI,
  claimRolePoolTasksAPI,
  getEligibleTransferUsersAPI,
  getTransferableTasksAPI,
  handoverWorkflowTasksAPI,
  returnDelegatedTasksAPI
} from '@/api/workflow'

const STAGE_LABELS = {
  reception: '客户专员',
  layout_assign: '预处理',
  project_manager: '项目经理',
  project_specialist: '项目专员',
  project_assistant: '项目助理',
  review: '译审',
  special_qc: '专检',
  layout: '排版',
  completed: '完成'
}

const DIFFICULTY_LABEL = { simple: '简单', normal: '普通', complex: '复杂' }
const DIFFICULTY_TYPE = { simple: 'success', normal: '', complex: 'danger' }

function formatStage(stageKey) {
  return STAGE_LABELS[stageKey] || stageKey || '-'
}

const props = defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] }
})

const emit = defineEmits(['open-chat', 'open-project', 'record-work', 'refresh'])
const canWriteProjects = hasPermission('projects:write')
const canOperateWorkflow = hasPermission(['projects:read', 'workflow:operate'])

function handleProjectStatusUpdated(row, payload) {
  const projectId = String(payload?.projectId || resolveProjectId(row) || '')
  if (projectId) {
    props.tasksList.forEach((item) => {
      if (String(resolveProjectId(item)) === projectId) {
        item.project_status = payload.status
      }
    })
  } else {
    row.project_status = payload.status
  }
  emit('refresh')
}
// 项目留言板块尚未开放，保留入口代码便于后续启用。
const projectMessageEnabled = false
// 流程阶段功能待启用，主表默认隐藏该列以节省横向空间，启用时改为 true。
const stageColumnEnabled = false

const selectedTasks = ref([])
const showAllTasks = ref(false)
const showDelegatedOnly = ref(false)
const currentPage = ref(1)
const PAGE_SIZE = 10
const claimingRolePool = ref(false)
const taskTableRef = ref(null)
const eligibleUsers = ref([])
const handoverVisible = ref(false)
const handoverTargetUserId = ref('')
const handoverType = ref('daily_shift')
const handoverReasonDetail = ref('')
const handoverTransferMode = ref('permanent')
const delegationEndAt = ref('')
const submittingHandover = ref(false)
const claimVisible = ref(false)
const claimLoading = ref(false)
const submittingClaim = ref(false)
const transferableTasks = ref([])
const claimSelectedTasks = ref([])
const currentUserId = (() => {
  try {
    return String(localStorage.getItem('user_id') || '')
  } catch {
    return ''
  }
})()

const emptyNote = () => ({
  content: '',
  contentJson: { type: 'doc', content: [{ type: 'paragraph' }] },
  attachments: []
})
const handoverNote = ref(emptyNote())
const claimNote = ref(emptyNote())
const claimFilters = reactive({ ownerUserId: '', keyword: '' })
const SEARCH_DEBOUNCE_MS = 400
let claimSearchTimer = null
let claimRequestId = 0
let claimController = null

const PROJECT_TYPE_OPTIONS = [
  { label: '笔译项目', value: 'translation' },
  { label: '口译项目', value: 'interpretation' },
  { label: '标注项目', value: 'annotation' },
  { label: '招聘项目', value: 'recruitment' }
]
const PROJECT_TYPE_VALUES = PROJECT_TYPE_OPTIONS.map(option => option.value)
const PROJECT_TYPE_LABELS = Object.fromEntries(PROJECT_TYPE_OPTIONS.map(option => [option.value, option.label]))

function projectStatusFilterKey(row) {
  const projectType = resolveProjectType(row)
  return `${projectType}:${normalizeProjectStatus(projectType, row?.project_status)}`
}

function isValidStoredStatusKey(value) {
  if (typeof value !== 'string') return false
  const [projectType, status] = value.split(':', 2)
  return PROJECT_TYPE_VALUES.includes(projectType) && !!status
}

function assigneeFilterKey(row) {
  if (row?.current_assignee_id) return `user:${row.current_assignee_id}`
  if (row?.current_assignee_name) return `name:${row.current_assignee_name}`
  return 'unassigned'
}

function isValidStoredAssigneeKey(value) {
  return typeof value === 'string' && (
    value === 'unassigned' || value.startsWith('user:') || value.startsWith('name:')
  )
}

// 筛选条件按“页面 + 当前用户”持久化，不同登录用户互不影响（例如只负责口译项目的用户）
const FILTER_STORAGE_KEY = `workbench-filters:my-tasks:${
  localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
}`

function readStoredFilters() {
  const fallback = { project_types: [], project_statuses: [], assignees: [], client: '', project: '', language_pair: '' }
  try {
    const raw = localStorage.getItem(FILTER_STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    return {
      project_types: Array.isArray(parsed.project_types)
        ? parsed.project_types.filter(value => PROJECT_TYPE_VALUES.includes(value))
        : [],
      project_statuses: Array.isArray(parsed.project_statuses)
        ? parsed.project_statuses.filter(isValidStoredStatusKey)
        : [],
      assignees: Array.isArray(parsed.assignees)
        ? parsed.assignees.filter(isValidStoredAssigneeKey)
        : [],
      client: typeof parsed.client === 'string' ? parsed.client : '',
      project: typeof parsed.project === 'string' ? parsed.project : '',
      language_pair: typeof parsed.language_pair === 'string' ? parsed.language_pair : ''
    }
  } catch {
    localStorage.removeItem(FILTER_STORAGE_KEY)
    return fallback
  }
}

const searchForm = reactive(readStoredFilters())
const projectSearchKeyword = computed(() => searchForm.project.trim())
const projectFilterActive = computed(() => !!(searchForm.project_types.length || projectSearchKeyword.value))

function clearProjectFilters() {
  searchForm.project_types = []
  searchForm.project = ''
}

function normalizeProjectSearch() {
  searchForm.project = projectSearchKeyword.value
}

const getTaskDeadline = getWorkItemDeadline
const deadlineState = getWorkItemDeadlineState

function isRolePoolTask(row) {
  return !row?.current_assignee_id && (
    row?.assignment_type === 'role_pool' || !!row?.group_assign_role
  )
}

function isDefaultVisibleTask(row) {
  if (isRolePoolTask(row)) return true
  if (row?.current_assignee_id && currentUserId) {
    return String(row.current_assignee_id) === currentUserId
  }
  return ['direct', 'project_role', 'delegated_out'].includes(row?.assignment_type)
}

function isCurrentUserResponsible(row) {
  if (row?.current_assignee_id && currentUserId) {
    return String(row.current_assignee_id) === currentUserId
  }
  // direct / project_role 均由后端按当前登录用户生成；兼容旧数据未返回负责人 ID 的情况。
  return ['direct', 'project_role'].includes(row?.assignment_type)
}

function compareProjectTasks(left, right, now) {
  const responsibilityDifference = Number(isCurrentUserResponsible(right)) - Number(isCurrentUserResponsible(left))
  if (responsibilityDifference) return responsibilityDifference
  return compareWorkItemsByDeadline(left, right, now)
}

const delegatedOutTasks = computed(() => props.tasksList.filter(row => row.assignment_type === 'delegated_out'))

const hiddenOverviewTaskCount = computed(() => (
  props.tasksList.filter(row => !isDefaultVisibleTask(row)).length
))

const projectStatusFilterOptions = computed(() => {
  const options = new Map()
  props.tasksList.forEach((row) => {
    const projectType = resolveProjectType(row)
    const status = normalizeProjectStatus(projectType, row?.project_status)
    if (!status) return
    const value = projectStatusFilterKey(row)
    const existing = options.get(value)
    if (existing) {
      existing.count += 1
      return
    }
    options.set(value, {
      value,
      label: `${PROJECT_TYPE_LABELS[projectType] || '项目'} · ${getProjectStatusLabel(projectType, status)}`,
      count: 1,
      projectType,
      status
    })
  })
  return Array.from(options.values()).sort((left, right) => {
    const typeDifference = PROJECT_TYPE_VALUES.indexOf(left.projectType) - PROJECT_TYPE_VALUES.indexOf(right.projectType)
    if (typeDifference) return typeDifference
    return left.label.localeCompare(right.label, 'zh-CN')
  })
})

const assigneeFilterOptions = computed(() => {
  const options = new Map()
  props.tasksList.forEach((row) => {
    const value = assigneeFilterKey(row)
    const existing = options.get(value)
    if (existing) {
      existing.count += 1
      return
    }
    options.set(value, {
      value,
      label: value === 'unassigned' ? '待认领（角色池）' : (row.current_assignee_name || '未知负责人'),
      count: 1
    })
  })
  return Array.from(options.values()).sort((left, right) => {
    if (left.value === 'unassigned') return 1
    if (right.value === 'unassigned') return -1
    return left.label.localeCompare(right.label, 'zh-CN')
  })
})

const filteredTasks = computed(() => {
  let list = showDelegatedOnly.value
    ? delegatedOutTasks.value
    : props.tasksList.filter(row => showAllTasks.value || isDefaultVisibleTask(row))

  if (searchForm.project_types.length) {
    list = list.filter(t => searchForm.project_types.includes(t.project_type || 'translation'))
  }
  if (searchForm.project_statuses.length) {
    list = list.filter(t => searchForm.project_statuses.includes(projectStatusFilterKey(t)))
  }
  if (searchForm.assignees.length) {
    list = list.filter(t => searchForm.assignees.includes(assigneeFilterKey(t)))
  }

  if (searchForm.client) {
    list = list.filter(t => [t.client_name, t.client_short_name].some(value => value && value.includes(searchForm.client)))
  }
  if (projectSearchKeyword.value) {
    list = list.filter(t => [t.project_name, t.sub_project_name, t.order_no].some(value => value && value.includes(projectSearchKeyword.value)))
  }
  if (searchForm.language_pair) {
    list = list.filter(t => t.language_pair && t.language_pair.includes(searchForm.language_pair))
  }
  const now = new Date()
  return list.sort((a, b) => compareProjectTasks(a, b, now))
})

const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredTasks.value.slice(start, start + PAGE_SIZE)
})

function clearTaskSelection() {
  selectedTasks.value = []
  taskTableRef.value?.clearSelection()
}

function toggleTaskScope() {
  showDelegatedOnly.value = false
  showAllTasks.value = !showAllTasks.value
  currentPage.value = 1
  clearTaskSelection()
}

function toggleDelegatedScope() {
  showDelegatedOnly.value = !showDelegatedOnly.value
  if (showDelegatedOnly.value) showAllTasks.value = false
  currentPage.value = 1
  clearTaskSelection()
}

function handlePageChange() {
  clearTaskSelection()
}

watch(searchForm, (value) => {
  currentPage.value = 1
  clearTaskSelection()
  try {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
      project_types: value.project_types.filter(item => PROJECT_TYPE_VALUES.includes(item)),
      project_statuses: value.project_statuses.filter(isValidStoredStatusKey),
      assignees: value.assignees.filter(isValidStoredAssigneeKey),
      client: value.client,
      project: value.project,
      language_pair: value.language_pair
    }))
  } catch {}
})

watch(() => filteredTasks.value.length, (total) => {
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (currentPage.value > lastPage) currentPage.value = lastPage
})

function rowClassName({ row }) {
  const state = deadlineState(row)
  if (state === DEADLINE_STATE.OVERDUE) return 'overdue-row'
  if (state === DEADLINE_STATE.URGENT) return 'urgent-row'
  if (row.delegation_overdue) return 'delegation-overdue-row'
  return ''
}

function hasAction(row, action) {
  return Array.isArray(row.available_actions) && row.available_actions.includes(action)
}

const directSelectedTasks = computed(() => selectedTasks.value.filter(
  row => row.assignment_type === 'direct' && !row.delegation_id
))
const rolePoolSelectedTasks = computed(() => selectedTasks.value.filter(isRolePoolTask))
const directSelectedRoleCodes = computed(() => new Set(
  directSelectedTasks.value.map(row => row.current_stage_role_code).filter(Boolean)
))
const handoverRoleName = computed(() => (
  directSelectedRoleCodes.value.size === 1
    ? directSelectedTasks.value[0]?.current_stage_role_name || ''
    : ''
))
const isTaskSelectable = (row) => (row.assignment_type === 'direct' && !row.delegation_id) || isRolePoolTask(row)

function assignmentTagType(row) {
  if (row.assignment_type === 'direct' || row.assignment_type === 'project_role') return 'success'
  if (isRolePoolTask(row)) return 'info'
  if (row.assignment_type === 'overview') return 'warning'
  if (row.assignment_type === 'delegated_out') return 'info'
  return 'info'
}

function assignmentLabel(row) {
  if (row.assignment_type === 'direct') return '直接负责'
  if (row.assignment_type === 'project_role') return '固定角色'
  if (isRolePoolTask(row)) return '角色池'
  if (row.assignment_type === 'overview') return '全局查看'
  if (row.assignment_type === 'delegated_out') return '我已委托'
  return '角色池'
}

function toggleTaskRowSelection(row, _column, event) {
  if (!isTaskSelectable(row)) return
  if (event?.target?.closest?.('button, a, input, textarea, select, label, .el-checkbox, .el-radio, .el-switch, .el-dropdown, .project-status-switch')) return
  const selected = selectedTasks.value.includes(row)
  taskTableRef.value?.toggleRowSelection(row, !selected)
}

const claimOwnerOptions = computed(() => {
  const owners = new Map()
  transferableTasks.value.forEach(task => {
    if (task.current_assignee_id && task.current_assignee_name) {
      owners.set(task.current_assignee_id, task.current_assignee_name)
    }
  })
  return Array.from(owners, ([id, name]) => ({ id, name }))
})

const openHandoverDialog = async () => {
  if (!directSelectedTasks.value.length) return
  if (directSelectedRoleCodes.value.size !== 1) {
    ElMessage.warning('一次只能交接同一角色类型的任务，请按角色分别选择')
    return
  }
  handoverTargetUserId.value = ''
  handoverType.value = 'daily_shift'
  handoverReasonDetail.value = ''
  handoverTransferMode.value = 'permanent'
  delegationEndAt.value = ''
  handoverNote.value = emptyNote()
  handoverVisible.value = true
  try {
    eligibleUsers.value = await getEligibleTransferUsersAPI(directSelectedTasks.value)
  } catch (error) {
    eligibleUsers.value = []
    ElMessage.error(error?.detail || error?.message || '加载可交接用户失败')
  }
}

const canSubmitHandover = computed(() => (
  !!handoverTargetUserId.value &&
  !!handoverType.value &&
  (handoverTransferMode.value !== 'delegation' || !!delegationEndAt.value) &&
  (handoverType.value !== 'other' || !!handoverReasonDetail.value.trim())
))

const submitHandover = async () => {
  if (!handoverTargetUserId.value || !directSelectedTasks.value.length) return
  submittingHandover.value = true
  try {
    await handoverWorkflowTasksAPI({
      items: directSelectedTasks.value,
      target_user_id: handoverTargetUserId.value,
      handover_type: handoverType.value,
      transfer_mode: handoverTransferMode.value,
      delegation_end_at: handoverTransferMode.value === 'delegation' ? delegationEndAt.value : undefined,
      reason_detail: handoverType.value === 'other' ? handoverReasonDetail.value.trim() : undefined,
      content: handoverNote.value.content,
      content_json: handoverNote.value.contentJson,
      attachment_ids: handoverNote.value.attachments.map(item => item.id)
    })
    ElMessage.success(`已发起 ${directSelectedTasks.value.length} 项任务交接，等待接收人确认`)
    handoverVisible.value = false
    selectedTasks.value = []
    taskTableRef.value?.clearSelection()
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '任务交接失败')
  } finally {
    submittingHandover.value = false
  }
}

const returnDelegation = async (row) => {
  if (!row.delegation_id) return
  try {
    await ElMessageBox.confirm(
      `确认将任务“${row.sub_project_name || row.project_name || row.order_no}”归还给${row.original_assignee_name || '原负责人'}吗？`,
      '归还临时代办任务',
      { type: 'warning', confirmButtonText: '确认归还', cancelButtonText: '取消' }
    )
    await returnDelegatedTasksAPI([row.delegation_id])
    ElMessage.success('任务已归还原负责人')
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || error?.message || '归还任务失败')
    }
  }
}

const claimSelectedRolePoolTasks = async () => {
  const tasks = [...rolePoolSelectedTasks.value]
  if (!tasks.length) return
  const manuscriptCount = tasks.filter(
    task => task.task_kind === 'manuscript_responsibility'
  ).length
  const workflowCount = tasks.length - manuscriptCount
  const claimDescription = [
    workflowCount ? `${workflowCount} 项工作流任务将由你直接负责` : '',
    manuscriptCount ? `${manuscriptCount} 个项目将绑定你为固定项目助理` : ''
  ].filter(Boolean).join('；')
  try {
    await ElMessageBox.confirm(
      `确认认领所选的 ${tasks.length} 项角色池任务吗？${claimDescription}。`,
      '认领角色池任务',
      { type: 'warning', confirmButtonText: '确认认领', cancelButtonText: '取消' }
    )
    claimingRolePool.value = true
    await claimRolePoolTasksAPI(tasks)
    ElMessage.success(`已认领 ${tasks.length} 项角色池任务`)
    selectedTasks.value = []
    taskTableRef.value?.clearSelection()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || error?.message || '认领任务失败')
    }
  } finally {
    claimingRolePool.value = false
  }
}

const loadTransferableTasks = async () => {
  claimController?.abort()
  claimController = new AbortController()
  const requestId = ++claimRequestId
  claimLoading.value = true
  claimSelectedTasks.value = []
  try {
    const rows = await getTransferableTasksAPI({
      owner_user_id: claimFilters.ownerUserId || undefined,
      keyword: claimFilters.keyword.trim() || undefined
    }, { signal: claimController.signal })
    if (requestId !== claimRequestId) return
    transferableTasks.value = Array.isArray(rows) ? rows : []
  } catch (error) {
    if (requestId !== claimRequestId || error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || error?.name === 'AbortError') return
    ElMessage.error(error?.detail || error?.message || '网络异常，可继承任务列表未刷新')
  } finally {
    if (requestId === claimRequestId) claimLoading.value = false
  }
}

const onClaimKeywordInput = (value) => {
  clearTimeout(claimSearchTimer)
  claimSearchTimer = null
  if (!String(value || '').trim()) {
    loadTransferableTasks()
    return
  }
  claimSearchTimer = setTimeout(() => {
    claimSearchTimer = null
    loadTransferableTasks()
  }, SEARCH_DEBOUNCE_MS)
}

const runClaimSearch = () => {
  clearTimeout(claimSearchTimer)
  claimSearchTimer = null
  loadTransferableTasks()
}

const openClaimDialog = () => {
  claimFilters.ownerUserId = ''
  claimFilters.keyword = ''
  claimNote.value = emptyNote()
  claimVisible.value = true
  loadTransferableTasks()
}

const submitClaim = async () => {
  if (!claimSelectedTasks.value.length) return
  submittingClaim.value = true
  try {
    await claimWorkflowTasksAPI({
      items: claimSelectedTasks.value,
      expected_assignee_ids: Object.fromEntries(
        claimSelectedTasks.value.map(task => [task.project_responsibility_id || task.workflow_instance_id, task.current_assignee_id])
      ),
      content: claimNote.value.content,
      content_json: claimNote.value.contentJson,
      attachment_ids: claimNote.value.attachments.map(item => item.id)
    })
    ElMessage.success(`已继承 ${claimSelectedTasks.value.length} 项任务`)
    claimVisible.value = false
    claimSelectedTasks.value = []
    emit('refresh')
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '任务继承失败')
  } finally {
    submittingClaim.value = false
  }
}

onBeforeUnmount(() => {
  clearTimeout(claimSearchTimer)
  claimController?.abort()
})
</script>

<style scoped>
.section-block { margin-bottom: 10px; }
.data-table { margin-bottom: 12px; }

.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.project-type-filter-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 12px;
}

.project-type-filter-group :deep(.el-checkbox) {
  margin-right: 0;
}

.project-status-filter-group,
.assignee-filter-group {
  display: grid;
  gap: 4px;
}

.project-status-filter-group :deep(.el-checkbox),
.assignee-filter-group :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
  white-space: normal;
}

.column-filter-empty {
  padding: 8px 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-align: center;
}

.task-toolbar__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.task-pagination {
  display: flex;
  justify-content: flex-end;
  margin: 0 0 12px;
}

.empty-tip {
  padding: 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.table-filter-empty {
  padding: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.dialog-alert {
  margin-bottom: 18px;
}

.handover-type-field {
  display: grid;
  gap: 10px;
  width: 100%;
}

.handover-type-field :deep(.el-radio-group) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}

.delegation-end-field {
  display: grid;
  gap: 6px;
  width: 100%;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.assignee-cell {
  display: grid;
  justify-items: start;
  gap: 1px;
}

.previous-assignee {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  line-height: 1.2;
}

.claim-search {
  margin: 16px 0 2px;
}

.claim-note {
  margin-top: 18px;
}

.claim-note__label {
  margin-bottom: 8px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

:deep(.overdue-row),
:deep(.overdue-row td) {
  background-color: var(--el-color-danger-light-9) !important;
}
:deep(.overdue-row:hover),
:deep(.overdue-row:hover td) {
  background-color: var(--el-color-danger-light-8) !important;
}

:deep(.urgent-row),
:deep(.urgent-row td) {
  background-color: var(--el-color-warning-light-9) !important;
}

:deep(.urgent-row:hover),
:deep(.urgent-row:hover td) {
  background-color: var(--el-color-warning-light-8) !important;
}

:deep(.delegation-overdue-row),
:deep(.delegation-overdue-row td) {
  background-color: var(--el-color-warning-light-9) !important;
}

@media (max-width: 720px) {
  .task-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .task-toolbar__actions {
    margin-left: 0;
    flex-wrap: wrap;
  }
}
</style>
