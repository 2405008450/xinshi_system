<template>
  <div class="section-block">
    <div class="task-toolbar">
      <p v-if="currentUserName" class="section-desc">当前用户：<strong>{{ currentUserName }}</strong></p>
      <div class="task-toolbar__actions">
        <el-button
          type="primary"
          :disabled="!selectedTasks.length"
          @click="openHandoverDialog"
        >
          交接所选任务（{{ selectedTasks.length }}）
        </el-button>
        <el-button type="warning" plain @click="openClaimDialog">继承他人任务</el-button>
      </div>
    </div>

    <el-form v-if="tasksList.length" :inline="true" :model="searchForm" size="small" class="task-search">
      <el-form-item label="客户">
        <el-input v-model="searchForm.client" placeholder="客户全称或简称" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item label="项目">
        <el-input v-model="searchForm.project" placeholder="项目名或订单号" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item label="语言对">
        <el-input v-model="searchForm.language_pair" placeholder="支持模糊搜索" clearable style="width: 140px" />
      </el-form-item>
    </el-form>

    <div v-if="urgentTasks.length" class="urgent-hint">
      <el-tag type="danger" size="small" effect="dark">紧急任务 {{ urgentTasks.length }}</el-tag>
      <span class="urgent-hint-text">高亮行为客户交稿时间在「当天至次日 10:00 前」的紧急任务，请优先处理。</span>
    </div>

    <el-table
      ref="taskTableRef"
      v-if="filteredTasks.length"
      :data="filteredTasks"
      border
      size="small"
      class="data-table"
      :row-class-name="rowClassName"
      @selection-change="selectedTasks = $event"
    >
      <el-table-column type="selection" width="48" :selectable="isTaskTransferable" />
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="类型" width="82">
        <template #default="{ row }">
          <el-tag :type="row.entity_type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
            {{ row.entity_type === 'suborder' ? '子订单' : '母项目' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="task_type" label="任务类型" width="120">
        <template #default="{ row }">{{ row.task_type || '项目任务' }}</template>
      </el-table-column>
      <el-table-column prop="client_name" label="客户全称" min-width="180" show-overflow-tooltip />
      <el-table-column prop="client_short_name" label="客户简称" width="120" show-overflow-tooltip />
      <el-table-column prop="project_name" label="母项目名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="sub_project_name" label="子项目名称" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.sub_project_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="order_no" label="订单编号" width="170" show-overflow-tooltip />
      <el-table-column prop="language_pair" label="语言对" width="140" show-overflow-tooltip />
      <el-table-column label="客户交稿时间" width="160">
        <template #default="{ row }">
          {{ formatDeadline(getTaskDeadline(row)) }}
        </template>
      </el-table-column>
      <el-table-column prop="current_stage_key" label="当前阶段" width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ STAGE_LABELS[row.current_stage_key] || row.current_stage_key }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="difficulty" label="难度" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
            {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="project_status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPE[row.project_status] || ''" size="small" effect="plain">
            {{ STATUS_LABEL[row.project_status] || row.project_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="分配" width="100">
        <template #default="{ row }">
          <el-tag :type="row.assignment_type === 'direct' ? 'success' : 'info'" size="small" effect="plain">
            {{ row.assignment_type === 'direct' ? '直接负责' : '角色池' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="$emit('enter-project', row)">进入</el-button>
          <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="$emit('open-chat', row.translation_project_id)">留言</el-button>
          <el-button type="success" link size="small" @click="$emit('record-work', row)">记进展</el-button>
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
              :label="user.full_name || user.username"
              :value="user.id"
              :disabled="String(user.id) === currentUserId"
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
        <el-table-column label="当前阶段" width="110">
          <template #default="{ row }">{{ STAGE_LABELS[row.current_stage_key] || row.current_stage_key }}</template>
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
const STATUS_LABEL = { pending: '待处理', in_progress: '进行中', completed: '已完成', paused: '暂停' }
const STATUS_TYPE = { pending: 'info', in_progress: '', completed: 'success', paused: 'warning' }

const props = defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] },
  /** 参考日期 YYYY-MM-DD，用于判定「当天及次日10点前」；不传则用当前真实日期 */
  referenceDate: { type: String, default: '' }
})

const emit = defineEmits(['enter-project', 'open-chat', 'record-work', 'refresh'])

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

/** 从任务对象取客户交稿时间（兼容接口 snake_case / camelCase） */
function getTaskDeadline(task) {
  return task?.customer_deadline_time ?? task?.customerDeadlineTime ?? null
}

/**
 * 判定是否为紧急任务：客户交稿时间在「参考日当天 00:00」到「参考日次日 10:00」之间。
 * @param {string|null} deadlineTime - ISO 或可解析的日期时间字符串
 * @param {string} [refDateStr] - 参考日期 YYYY-MM-DD，不传则用当前日期
 */
function isUrgentTask(deadlineTime, refDateStr) {
  if (!deadlineTime) return false
  const deadline = new Date(deadlineTime)
  if (isNaN(deadline.getTime())) return false

  const ref = refDateStr && refDateStr.trim() ? new Date(refDateStr + 'T00:00:00') : new Date()
  const today = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate())
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)

  const deadlineCutoff = new Date(tomorrow)
  deadlineCutoff.setHours(10, 0, 0, 0)

  return deadline >= today && deadline <= deadlineCutoff
}

const refDate = computed(() => (props.referenceDate || '').trim() || null)

function isRowUrgent(task) {
  return isUrgentTask(getTaskDeadline(task), refDate.value)
}

const urgentTasks = computed(() => props.tasksList.filter(isRowUrgent))

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
  // 紧急任务置顶，便于一眼看到高亮行
  return list.sort((a, b) => Number(isRowUrgent(b)) - Number(isRowUrgent(a)))
})

function rowClassName({ row }) {
  return isRowUrgent(row) ? 'urgent-row' : ''
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
.section-block { margin-bottom: 28px; }
.section-desc { margin: 0 0 8px 0; line-height: 1.6; color: var(--el-text-color-regular); }
.data-table { margin-bottom: 12px; }

.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.task-toolbar .section-desc {
  margin: 0;
}

.task-toolbar__actions {
  display: flex;
  gap: 8px;
}

.task-search {
  margin-bottom: -6px;
}

.urgent-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: var(--el-color-danger-light-9);
  border-left: 3px solid var(--el-color-danger);
  border-radius: 4px;
}
.urgent-hint-text {
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.empty-tip {
  padding: 20px;
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

:deep(.urgent-row),
:deep(.urgent-row td) {
  background-color: var(--el-color-danger-light-9) !important;
}
:deep(.urgent-row:hover),
:deep(.urgent-row:hover td) {
  background-color: var(--el-color-danger-light-8) !important;
}

@media (max-width: 720px) {
  .task-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .task-toolbar__actions {
    flex-wrap: wrap;
  }
}
</style>
