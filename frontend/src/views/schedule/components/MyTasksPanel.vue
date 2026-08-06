<template>
  <div class="section-block">
    <div class="task-toolbar">
      <div v-if="tasksList.length" class="task-filters">
        <el-input v-model="searchForm.client" aria-label="按客户筛选" placeholder="客户简称" clearable size="small" />
        <el-input
          v-model="searchForm.project"
          aria-label="按项目筛选"
          placeholder="项目、子项目或订单号"
          clearable
          size="small"
          class="task-filters__project"
        />
        <el-input v-model="searchForm.language_pair" aria-label="按语言对筛选" placeholder="语言对" clearable size="small" />
      </div>
      <div class="task-toolbar__actions">
        <el-button
          type="primary"
          size="small"
          :disabled="!selectedTasks.length"
          @click="openHandoverDialog"
        >
          交接所选任务（{{ selectedTasks.length }}）
        </el-button>
        <el-button type="warning" plain size="small" @click="openClaimDialog">继承他人任务</el-button>
      </div>
    </div>

    <el-table
      ref="taskTableRef"
      v-if="filteredTasks.length"
      :data="filteredTasks"
      border
      size="small"
      class="data-table workbench-data-table"
      :row-class-name="rowClassName"
      @selection-change="selectedTasks = $event"
    >
      <el-table-column type="selection" width="48" :selectable="isTaskTransferable" />
      <el-table-column type="index" label="序号" width="56" />
      <el-table-column prop="order_no" label="订单号" width="180" show-overflow-tooltip />
      <el-table-column label="项目 / 任务" min-width="280">
        <template #default="{ row }">
          <div class="workbench-project-cell">
            <span class="workbench-project-cell__title">
              {{ row.entity_type === 'suborder' ? (row.sub_project_name || row.project_name || '-') : (row.project_name || '-') }}
            </span>
            <div class="workbench-project-cell__meta">
              <el-tag :type="row.entity_type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
                {{ row.entity_type === 'suborder' ? '子订单' : '母项目' }}
              </el-tag>
              <span>{{ row.task_type || '项目任务' }}</span>
              <span v-if="row.entity_type === 'suborder' && row.project_name">母项目：{{ row.project_name }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="客户" width="130" show-overflow-tooltip>
        <template #default="{ row }">{{ row.client_short_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="客户交稿" width="170">
        <template #default="{ row }">
          <div class="deadline-cell">
            <span>{{ formatDeadline(getTaskDeadline(row)) }}</span>
            <el-tag v-if="deadlineState(row) === DEADLINE_STATE.OVERDUE" type="danger" size="small" effect="dark">已逾期</el-tag>
            <el-tag v-else-if="deadlineState(row) === DEADLINE_STATE.URGENT" type="warning" size="small" effect="dark">24小时内</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="current_stage_key" label="状态" width="112">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ formatStage(row.current_stage_key) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="showAssigneeColumn" prop="current_assignee_name" label="当前负责人" width="120">
        <template #default="{ row }">{{ row.current_assignee_name || '角色池' }}</template>
      </el-table-column>
      <el-table-column prop="language_pair" label="语言对" width="120" show-overflow-tooltip />
      <el-table-column prop="difficulty" label="难度" width="76">
        <template #default="{ row }">
          <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
            {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="分配" width="92">
        <template #default="{ row }">
          <el-tag :type="row.assignment_type === 'direct' ? 'success' : row.assignment_type === 'overview' ? 'warning' : 'info'" size="small" effect="plain">
            {{ row.assignment_type === 'direct' ? '直接负责' : row.assignment_type === 'overview' ? '全局查看' : '角色池' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="128" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="$emit('open-chat', row.translation_project_id)">留言</el-button>
          <el-button v-if="row.assignment_type !== 'overview'" type="success" link size="small" @click="$emit('record-work', row)">记进展</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-else-if="currentUserName" class="empty-tip">暂无待处理的工作流任务。</div>
    <el-empty v-else description="请先登录，登录账号将用于匹配「我的任务」" />

    <el-dialog v-model="handoverVisible" title="交接所选任务" width="720px" destroy-on-close>
      <el-alert
        :title="`将 ${selectedTasks.length} 项任务交接给其他负责人，提交后立即生效。`"
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
        <el-table-column label="状态" width="110">
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
import { ElMessage } from 'element-plus'
import TransferNoteEditor from '@/components/TransferNoteEditor.vue'
import {
  DEADLINE_STATE,
  compareWorkItemsByDeadline,
  getWorkItemDeadline,
  getWorkItemDeadlineState
} from '@/utils/workItemDeadline'
import {
  claimWorkflowTasksAPI,
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

const DIFFICULTY_LABEL = { simple: '简单', normal: '普通', complex: '复杂' }
const DIFFICULTY_TYPE = { simple: 'success', normal: '', complex: 'danger' }

function formatStage(stageKey) {
  return STAGE_LABELS[stageKey] || stageKey || '-'
}

const props = defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] }
})

const emit = defineEmits(['open-chat', 'record-work', 'refresh'])

const selectedTasks = ref([])
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

const showAssigneeColumn = computed(() => (
  props.tasksList.some(task => task.assignment_type === 'overview')
))

function rowClassName({ row }) {
  const state = deadlineState(row)
  if (state === DEADLINE_STATE.OVERDUE) return 'overdue-row'
  if (state === DEADLINE_STATE.URGENT) return 'urgent-row'
  return ''
}

const isTaskTransferable = (row) => row.assignment_type === 'direct'

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
  if (!selectedTasks.value.length) return
  handoverTargetUserId.value = ''
  handoverType.value = 'daily_shift'
  handoverReasonDetail.value = ''
  handoverNote.value = emptyNote()
  handoverVisible.value = true
  try {
    eligibleUsers.value = await getEligibleTransferUsersAPI(
      selectedTasks.value.map(task => task.workflow_instance_id)
    )
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
  if (!handoverTargetUserId.value || !selectedTasks.value.length) return
  submittingHandover.value = true
  try {
    await handoverWorkflowTasksAPI({
      workflow_instance_ids: selectedTasks.value.map(task => task.workflow_instance_id),
      target_user_id: handoverTargetUserId.value,
      handover_type: handoverType.value,
      reason_detail: handoverType.value === 'other' ? handoverReasonDetail.value.trim() : undefined,
      content: handoverNote.value.content,
      content_json: handoverNote.value.contentJson,
      attachment_ids: handoverNote.value.attachments.map(item => item.id)
    })
    ElMessage.success(`已发起 ${selectedTasks.value.length} 项任务交接，等待接收人确认`)
    handoverVisible.value = false
    selectedTasks.value = []
    taskTableRef.value?.clearSelection()
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '任务交接失败')
  } finally {
    submittingHandover.value = false
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
      workflow_instance_ids: claimSelectedTasks.value.map(task => task.workflow_instance_id),
      expected_assignee_ids: Object.fromEntries(
        claimSelectedTasks.value.map(task => [task.workflow_instance_id, task.current_assignee_id])
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
