<template>
  <div class="section-block">
    <div class="task-toolbar">
      <div v-if="tasksList.length" class="task-filters">
        <el-select v-model="searchForm.project_type" placeholder="项目类型" clearable size="small" style="width: 120px">
          <el-option label="笔译项目" value="translation" />
          <el-option label="口译项目" value="interpretation" />
          <el-option label="标注项目" value="annotation" />
          <el-option label="招聘项目" value="recruitment" />
        </el-select>
        <el-input v-model="searchForm.client" aria-label="按客户筛选" placeholder="客户简称" clearable size="small" />
        <el-input
          v-model="searchForm.project"
          aria-label="按项目筛选"
          placeholder="项目、子项目或订单号"
          clearable
          size="small"
          class="task-filters__project"
        />
        <el-input v-model="searchForm.language_pair" aria-label="按翻译方向筛选" placeholder="翻译方向" clearable size="small" />
      </div>
      <div class="task-toolbar__actions">
        <el-button
          type="primary"
          size="small"
          :disabled="!directSelectedTasks.length"
          @click="openHandoverDialog"
        >
          交接所选任务（{{ directSelectedTasks.length }}）
        </el-button>
        <el-button
          type="success"
          plain
          size="small"
          :loading="claimingRolePool"
          :disabled="!rolePoolSelectedTasks.length"
          @click="claimSelectedRolePoolTasks"
        >认领任务（{{ rolePoolSelectedTasks.length }}）</el-button>
        <el-button type="warning" plain size="small" @click="openClaimDialog">继承他人任务</el-button>
      </div>
    </div>

    <el-table
      ref="taskTableRef"
      v-if="filteredTasks.length"
      :data="filteredTasks"
      border
      size="small"
      class="data-table workbench-data-table row-click-select-table"
      :row-class-name="rowClassName"
      @selection-change="selectedTasks = $event"
      @row-click="toggleTaskRowSelection"
    >
      <el-table-column type="selection" :width="WORKBENCH_COLUMN_WIDTHS.selection" :selectable="isTaskSelectable" />
      <el-table-column type="index" label="序号" :width="WORKBENCH_COLUMN_WIDTHS.index" />
      <el-table-column prop="order_no" label="订单号" :width="WORKBENCH_COLUMN_WIDTHS.orderNo" show-overflow-tooltip />
      <el-table-column label="项目 / 任务" :width="WORKBENCH_COLUMN_WIDTHS.projectTask">
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
        <template #default="{ row }">{{ row.client_short_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="计划节点" :width="WORKBENCH_COLUMN_WIDTHS.customerDeadline">
        <template #default="{ row }">
          <div class="deadline-cell">
            <span>{{ formatDeadline(getTaskDeadline(row)) }}</span>
            <el-tag v-if="deadlineState(row) === DEADLINE_STATE.OVERDUE" type="danger" size="small" effect="dark">已逾期</el-tag>
            <el-tag v-else-if="deadlineState(row) === DEADLINE_STATE.URGENT" type="warning" size="small" effect="dark">24小时内</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="project_status" label="项目状态" :width="WORKBENCH_COLUMN_WIDTHS.projectStatus">
        <template #default="{ row }">
          <el-tag :type="getProjectStatusType(row.project_status)" size="small" effect="plain">
            {{ getProjectStatusLabel(row.project_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="language_pair" label="语言方向" :width="WORKBENCH_COLUMN_WIDTHS.languagePair">
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
        <template #default="{ row }">
          <ProjectRoleAssigneesPopover
            :current-assignee-name="row.current_assignee_name || ''"
            :current-stage-role-code="row.current_stage_role_code || ''"
            :current-stage-role-name="row.current_stage_role_name || ''"
            :group-assign-role="row.group_assign_role || ''"
            :role-assignments="row.role_assignments || []"
          />
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
      <el-table-column label="操作" width="150" align="center" fixed="right">
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
        </template>
      </el-table-column>
    </el-table>
    <div v-else-if="currentUserName" class="empty-tip">暂无待处理任务或可认领的角色池任务。</div>
    <el-empty v-else description="请先登录，登录账号将用于匹配「我的任务」" />

    <el-dialog v-model="handoverVisible" title="交接所选任务" width="720px" destroy-on-close>
      <el-alert
        :title="`将 ${directSelectedTasks.length} 项${handoverRoleName || ''}任务交接给相同角色的其他负责人，接收人确认后生效。`"
        type="warning"
        :closable="false"
        show-icon
        class="dialog-alert"
      />
      <el-form label-width="92px">
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
          <el-select v-model="claimFilters.ownerUserId" clearable filterable placeholder="全部" style="width: 180px">
            <el-option v-for="owner in claimOwnerOptions" :key="owner.id" :label="owner.name" :value="owner.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="claimFilters.keyword" clearable placeholder="客户、项目或订单号" style="width: 240px" @keyup.enter="loadTransferableTasks" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="claimLoading" @click="loadTransferableTasks">查询</el-button>
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
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TransferNoteEditor from '@/components/TransferNoteEditor.vue'
import LanguagePairText from '@/components/common/LanguagePairText.vue'
import { WORKBENCH_COLUMN_WIDTHS } from '@/constants/workbenchColumns'
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
  handoverWorkflowTasksAPI
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

const PROJECT_STATUS_LABELS = {
  initial_follow_up: '初步跟进',
  ended: '口译结束',
  settled: '已结算',
  trial: '试标中',
  sent_to_client: '已发客户',
  pending_setup: '新建待立项',
  sourcing: '寻访阶段',
  recommending: '简历推荐中',
  interviewing: '面试进行中',
  offer_negotiation: 'Offer谈判',
  pending_onboard: '候选人待入职',
  probation: '已入职保用期',
  closed: '项目结案',
  pending: '待确认',
  pending_confirmation: '待确认',
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果',
  resource_sourcing: '资源开拓', resource_sourcing_cancelled: '取消资源开拓',
  trial_preparation: '试标准备', trial_in_progress: '试标中', trial_passed: '试标通过',
  trial_failed: '试标未通过', trial_partially_passed: '部分试标通过', project_in_progress: '项目进行中',
  in_progress: '已确认',
  confirmed: '已确认',
  organized: '已整理',
  translator_assigned: '已排译员',
  sent_to_translator: '已发译员',
  translator_returned: '译员发回',
  special_checked: '已专检',
  typeset: '已排版',
  special_checked_typeset: '已专检排版',
  reviewed: '已审核',
  completed: '已发客户',
  sent_to_client: '已发客户',
  client_feedback: '客户反馈',
  feedback_sent_to_client: '反馈后发客户',
  cancelled: '已取消',
  partially_cancelled: '已部分取消',
  terminated: '已取消',
  paused: '已暂停'
}

const PROJECT_STATUS_TYPES = {
  initial_follow_up: 'warning', ended: 'success', settled: 'success', trial: 'warning',
  pending_setup: 'info', sourcing: 'primary', recommending: 'warning', interviewing: 'warning',
  offer_negotiation: 'warning', pending_onboard: 'primary', probation: 'success', closed: 'success',
  pending: 'info', pending_confirmation: 'info',
  initial_consultation: 'info', consultation_no_result: 'info', resource_sourcing: 'primary',
  resource_sourcing_cancelled: 'danger', trial_preparation: 'warning', trial_in_progress: 'warning',
  trial_passed: 'success', trial_failed: 'danger', trial_partially_passed: 'warning', project_in_progress: 'primary',
  confirmed: 'primary', in_progress: 'primary', organized: 'primary',
  translator_assigned: 'warning', sent_to_translator: 'warning',
  translator_returned: 'primary', special_checked: 'primary', typeset: 'primary',
  special_checked_typeset: 'primary', reviewed: 'success', completed: 'success',
  sent_to_client: 'success', client_feedback: 'success', feedback_sent_to_client: 'success',
  cancelled: 'danger', partially_cancelled: 'danger', terminated: 'danger', paused: 'warning'
}

const DIFFICULTY_LABEL = { simple: '简单', normal: '普通', complex: '复杂' }
const DIFFICULTY_TYPE = { simple: 'success', normal: '', complex: 'danger' }

function formatStage(stageKey) {
  return STAGE_LABELS[stageKey] || stageKey || '-'
}

const getProjectStatusLabel = (status) => PROJECT_STATUS_LABELS[status] || status || '-'
const getProjectStatusType = (status) => PROJECT_STATUS_TYPES[status] || 'info'

const props = defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] }
})

const emit = defineEmits(['open-chat', 'open-project', 'record-work', 'refresh'])
// 项目留言板块尚未开放，保留入口代码便于后续启用。
const projectMessageEnabled = false
// 流程阶段功能待启用，主表默认隐藏该列以节省横向空间，启用时改为 true。
const stageColumnEnabled = false

const selectedTasks = ref([])
const claimingRolePool = ref(false)
const taskTableRef = ref(null)
const eligibleUsers = ref([])
const handoverVisible = ref(false)
const handoverTargetUserId = ref('')
const handoverType = ref('daily_shift')
const handoverReasonDetail = ref('')
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

const searchForm = reactive({
  project_type: '',
  client: '',
  project: '',
  language_pair: ''
})

function formatDeadline(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  if (isNaN(d.getTime())) return timeStr
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

const getTaskDeadline = getWorkItemDeadline
const deadlineState = getWorkItemDeadlineState

const filteredTasks = computed(() => {
  let list = props.tasksList.slice()

  if (searchForm.project_type) {
    list = list.filter(t => (t.project_type || 'translation') === searchForm.project_type)
  }

  if (searchForm.client) {
    list = list.filter(t => [t.client_name, t.client_short_name].some(value => value && value.includes(searchForm.client)))
  }
  if (searchForm.project) {
    list = list.filter(t => [t.project_name, t.sub_project_name, t.order_no].some(value => value && value.includes(searchForm.project)))
  }
  if (searchForm.language_pair) {
    list = list.filter(t => t.language_pair && t.language_pair.includes(searchForm.language_pair))
  }
  const now = new Date()
  return list.sort((a, b) => compareWorkItemsByDeadline(a, b, now))
})

function rowClassName({ row }) {
  const state = deadlineState(row)
  if (state === DEADLINE_STATE.OVERDUE) return 'overdue-row'
  if (state === DEADLINE_STATE.URGENT) return 'urgent-row'
  return ''
}

const directSelectedTasks = computed(() => selectedTasks.value.filter(row => row.assignment_type === 'direct'))
const rolePoolSelectedTasks = computed(() => selectedTasks.value.filter(row => row.assignment_type === 'role_pool'))
const directSelectedRoleCodes = computed(() => new Set(
  directSelectedTasks.value.map(row => row.current_stage_role_code).filter(Boolean)
))
const handoverRoleName = computed(() => (
  directSelectedRoleCodes.value.size === 1
    ? directSelectedTasks.value[0]?.current_stage_role_name || ''
    : ''
))
const isTaskSelectable = (row) => ['direct', 'role_pool'].includes(row.assignment_type)

function assignmentTagType(row) {
  if (row.assignment_type === 'direct' || row.assignment_type === 'project_role') return 'success'
  if (row.assignment_type === 'overview') return 'warning'
  return 'info'
}

function assignmentLabel(row) {
  if (row.assignment_type === 'direct') return '直接负责'
  if (row.assignment_type === 'project_role') return '固定角色'
  if (row.assignment_type === 'overview') return '全局查看'
  return '角色池'
}

function toggleTaskRowSelection(row, _column, event) {
  if (!isTaskSelectable(row)) return
  if (event?.target?.closest?.('button, a, input, textarea, select, label, .el-checkbox, .el-radio, .el-switch')) return
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
  claimLoading.value = true
  claimSelectedTasks.value = []
  try {
    transferableTasks.value = await getTransferableTasksAPI({
      owner_user_id: claimFilters.ownerUserId || undefined,
      keyword: claimFilters.keyword || undefined
    })
  } catch (error) {
    transferableTasks.value = []
    ElMessage.error(error?.detail || error?.message || '加载可继承任务失败')
  } finally {
    claimLoading.value = false
  }
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

.task-filters {
  display: grid;
  grid-template-columns: 150px 220px 130px;
  gap: 8px;
  min-width: 0;
}

.task-filters__project {
  min-width: 0;
}

.task-toolbar__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.deadline-cell {
  display: grid;
  justify-items: start;
  gap: 4px;
  font-size: 12px;
}

.empty-tip {
  padding: 12px;
  text-align: center;
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

@media (max-width: 720px) {
  .task-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .task-filters {
    grid-template-columns: 1fr;
    width: 100%;
  }

  .task-toolbar__actions {
    margin-left: 0;
    flex-wrap: wrap;
  }
}
</style>
