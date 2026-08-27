<template>
  <div class="management-handover">
    <div v-if="incomingRequests.length" class="incoming-list">
      <div class="panel-title">
        待确认的管理层交接
        <el-tag type="warning" size="small">{{ incomingRequests.length }}</el-tag>
      </div>
      <el-card
        v-for="request in incomingRequests"
        :key="request.id"
        shadow="never"
        class="request-card"
      >
        <div class="request-header">
          <div>
            <strong>{{ request.requester_name || '未知发起人' }}</strong>
            <span>向你交接 {{ request.projects?.length || 0 }} 个管理项目</span>
          </div>
          <span class="request-time">{{ formatDateTime(request.created_at) }}</span>
        </div>
        <div v-if="request.reason" class="request-note">原因：{{ request.reason }}</div>
        <div v-if="request.note" class="request-note">说明：{{ request.note }}</div>
        <el-table :data="request.projects || []" border size="small" class="request-projects">
          <el-table-column prop="order_no" label="订单号" width="145" show-overflow-tooltip />
          <el-table-column prop="project_name" label="项目名称" min-width="170" show-overflow-tooltip />
          <el-table-column prop="client_short_name" label="客户" width="100" show-overflow-tooltip />
          <el-table-column label="客户交稿" width="145">
            <template #default="{ row }">{{ formatDateTime(row.customer_deadline_time) }}</template>
          </el-table-column>
          <el-table-column label="项目状态" width="100">
            <template #default="{ row }"><el-tag :type="getProjectStatusType(row.project_status)" size="small" effect="plain">{{ getProjectStatusLabel(row.project_status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="翻译方向" width="105">
            <template #default="{ row }"><LanguagePairText :value="row.language_pair" /></template>
          </el-table-column>
          <el-table-column label="难度" width="68">
            <template #default="{ row }">
              <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
                {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="request-actions">
          <el-button size="small" type="danger" plain @click="decideRequest(request, 'reject')">拒绝</el-button>
          <el-button size="small" type="primary" @click="decideRequest(request, 'accept')">确认接收</el-button>
        </div>
      </el-card>
    </div>

    <div class="panel-title">
      <span>我负责及可承接的管理项目</span>
      <div class="panel-actions">
        <el-button
          v-if="canSelfClaim"
          type="success"
          plain
          size="small"
          :loading="claiming"
          :disabled="!claimableSelectedProjects.length"
          @click="claimSelectedProjects"
        >
          自主承接（{{ claimableSelectedProjects.length }}）
        </el-button>
        <el-button
          type="primary"
          size="small"
          :disabled="!handoverSelectedProjects.length"
          @click="openHandoverDialog"
        >
          交接管理归属（{{ handoverSelectedProjects.length }}）
        </el-button>
      </div>
    </div>

    <el-table
      ref="projectTableRef"
      v-loading="loading"
      :data="projects"
      border
      size="small"
      max-height="460"
      class="workbench-data-table row-click-select-table"
      :row-key="row => `${row.project_type || 'translation'}:${row.project_id || row.translation_project_id}`"
      @selection-change="selectedProjects = $event"
      @row-click="toggleProjectRowSelection"
    >
      <el-table-column type="selection" :width="WORKBENCH_COLUMN_WIDTHS.selection" />
      <el-table-column type="index" label="序号" :width="WORKBENCH_COLUMN_WIDTHS.index" />
      <el-table-column prop="order_no" label="订单号" :width="WORKBENCH_COLUMN_WIDTHS.orderNo" show-overflow-tooltip />
      <el-table-column label="项目类型" width="90">
        <template #default="{ row }"><el-tag type="info" size="small" effect="plain">{{ row.project_type_label || '笔译项目' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="项目 / 任务" :width="WORKBENCH_COLUMN_WIDTHS.projectTask">
        <template #default="{ row }">
          <div class="workbench-project-cell">
            <span class="workbench-project-cell__title" :title="row.project_name || '-'">{{ row.project_name || '-' }}</span>
            <div class="workbench-project-cell__meta">
              <el-tag size="small" effect="plain">母项目</el-tag>
              <span>{{ row.task_type || '项目任务' }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="client_short_name" label="客户" :width="WORKBENCH_COLUMN_WIDTHS.client" show-overflow-tooltip />
      <el-table-column label="客户交稿" :width="WORKBENCH_COLUMN_WIDTHS.customerDeadline">
        <template #default="{ row }">{{ formatDateTime(row.customer_deadline_time) }}</template>
      </el-table-column>
      <el-table-column label="项目状态" :width="WORKBENCH_COLUMN_WIDTHS.projectStatus">
        <template #default="{ row }"><el-tag :type="getProjectStatusType(row.project_status)" size="small" effect="plain">{{ getProjectStatusLabel(row.project_status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="翻译方向" :width="WORKBENCH_COLUMN_WIDTHS.languagePair">
        <template #default="{ row }"><LanguagePairText :value="row.language_pair" /></template>
      </el-table-column>
      <el-table-column label="难度" :width="WORKBENCH_COLUMN_WIDTHS.difficulty">
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
      <el-table-column prop="project_manager_name" label="管理归属" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.project_manager_id" type="success" size="small" effect="plain">
            {{ row.project_manager_name || '已绑定' }}
          </el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">未绑定·可承接</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click.stop="$emit('open-project', row)">进入项目</el-button>
          <el-button v-if="canRecordProgress(row)" type="primary" link size="small" @click.stop="openProgressDialog(row)">记录进展</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !projects.length" description="暂无负责或可承接的管理项目" :image-size="72" />

    <el-dialog
      v-model="dialogVisible"
      title="发起管理层项目归属交接"
      width="620px"
      destroy-on-close
    >
      <el-alert
        :title="`将 ${handoverProjects.length} 个项目的管理主负责人交接给另一位项目经理，需由接收人确认。`"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-width="100px" class="handover-form">
        <el-form-item label="接收经理" required>
          <el-select
            v-model="targetManagerId"
            filterable
            placeholder="请选择项目经理"
            style="width: 100%"
          >
            <el-option
              v-for="manager in managerCandidates"
              :key="manager.id"
              :label="manager.is_on_leave ? `${manager.full_name || manager.username}（请假至 ${formatDateTime(manager.leave_end)}）` : (manager.full_name || manager.username)"
              :value="manager.id"
              :disabled="manager.is_on_leave"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="交接原因">
          <el-input v-model="reason" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="交接说明">
          <el-input v-model="note" type="textarea" :rows="4" maxlength="5000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!targetManagerId"
          @click="submitHandover"
        >
          发起管理层交接
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="progressVisible" title="记录管理项目进展" width="min(560px, calc(100vw - 32px))">
      <el-form label-width="90px">
        <el-form-item label="项目"><el-input :model-value="progressProject?.project_name || progressProject?.order_no" disabled /></el-form-item>
        <el-form-item label="工作日期" required><el-date-picker v-model="progressForm.work_date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="进展内容" required><el-input v-model="progressForm.progress_content" type="textarea" :rows="4" maxlength="10000" show-word-limit /></el-form-item>
        <el-form-item label="耗时（分钟）"><el-input-number v-model="progressForm.duration_minutes" :min="0" :max="1440" style="width: 100%" /></el-form-item>
        <el-form-item label="工作结果"><el-input v-model="progressForm.result_content" type="textarea" :rows="2" maxlength="10000" show-word-limit /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressVisible = false">取消</el-button>
        <el-button type="primary" :loading="progressSubmitting" @click="submitProgress">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  acceptProjectManagerHandoverAPI,
  claimManagementProjectsAPI,
  createProjectManagerHandoverAPI,
  getIncomingProjectManagerHandoversAPI,
  getManagementProjectsAPI,
  getProjectManagerCandidatesAPI,
  rejectProjectManagerHandoverAPI
} from '@/api/workflow'
import { hasRole } from '@/utils/permission'
import { createWorkEntry } from '@/api/tasks'
import LanguagePairText from '@/components/common/LanguagePairText.vue'
import { WORKBENCH_COLUMN_WIDTHS } from '@/constants/workbenchColumns'
import ProjectRoleAssigneesPopover from './ProjectRoleAssigneesPopover.vue'

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

const getProjectStatusLabel = (status) => PROJECT_STATUS_LABELS[status] || status || '-'
const getProjectStatusType = (status) => PROJECT_STATUS_TYPES[status] || 'info'

const emit = defineEmits(['updated', 'open-project'])
const currentUserId = localStorage.getItem('user_id') || ''
const projects = ref([])
const incomingRequests = ref([])
const managerCandidates = ref([])
const progressVisible = ref(false)
const progressSubmitting = ref(false)
const progressProject = ref(null)
const progressForm = ref({ work_date: '', progress_content: '', duration_minutes: 0, result_content: '' })
const localDate = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
const canRecordProgress = (row) => Boolean(row.project_responsibility_id && String(row.project_manager_id || '') === currentUserId)
const openProgressDialog = (row) => {
  progressProject.value = row
  progressForm.value = { work_date: localDate(), progress_content: '', duration_minutes: 0, result_content: '' }
  progressVisible.value = true
}
const submitProgress = async () => {
  if (!progressForm.value.work_date || !progressForm.value.progress_content.trim()) return ElMessage.warning('请填写工作日期和进展内容')
  progressSubmitting.value = true
  try {
    await createWorkEntry({
      ...progressForm.value,
      progress_content: progressForm.value.progress_content.trim(),
      result_content: progressForm.value.result_content.trim() || null,
      project_responsibility_id: progressProject.value.project_responsibility_id
    })
    ElMessage.success('管理项目进展已记录')
    progressVisible.value = false
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '记录进展失败')
  } finally {
    progressSubmitting.value = false
  }
}
const selectedProjects = ref([])
const handoverProjects = ref([])
const projectTableRef = ref(null)
const loading = ref(false)
const submitting = ref(false)
const claiming = ref(false)
const dialogVisible = ref(false)
const targetManagerId = ref('')
const reason = ref('')
const note = ref('')
const canSelfClaim = hasRole('项目经理')
const claimableSelectedProjects = computed(() => (
  canSelfClaim
    ? selectedProjects.value.filter(project => !project.project_manager_id)
    : []
))
const handoverSelectedProjects = computed(() => (
  selectedProjects.value.filter(project => project.project_manager_id || !canSelfClaim)
))

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = item => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadData() {
  loading.value = true
  try {
    const [managed, incoming] = await Promise.all([
      getManagementProjectsAPI(),
      getIncomingProjectManagerHandoversAPI()
    ])
    projects.value = Array.isArray(managed) ? managed : []
    incomingRequests.value = Array.isArray(incoming) ? incoming : []
  } catch (error) {
    projects.value = []
    incomingRequests.value = []
    ElMessage.error(error?.detail || error?.message || '加载管理层项目交接失败')
  } finally {
    loading.value = false
  }
}

async function openHandoverDialog() {
  if (!handoverSelectedProjects.value.length) return
  handoverProjects.value = [...handoverSelectedProjects.value]
  targetManagerId.value = ''
  reason.value = ''
  note.value = ''
  try {
    const response = await getProjectManagerCandidatesAPI()
    managerCandidates.value = Array.isArray(response) ? response : []
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '加载项目经理列表失败')
  }
}

async function submitHandover() {
  if (!targetManagerId.value || !handoverProjects.value.length) return
  submitting.value = true
  try {
    await createProjectManagerHandoverAPI({
      project_refs: handoverProjects.value.map(item => ({
        project_type: item.project_type || 'translation',
        project_id: item.project_id || item.translation_project_id
      })),
      target_manager_id: targetManagerId.value,
      reason: reason.value.trim() || undefined,
      note: note.value.trim() || undefined
    })
    ElMessage.success('管理层项目交接已发起，等待接收经理确认')
    dialogVisible.value = false
    clearProjectSelection()
    await loadData()
    emit('updated')
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '发起管理层项目交接失败')
  } finally {
    submitting.value = false
  }
}

function clearProjectSelection() {
  selectedProjects.value = []
  handoverProjects.value = []
  projectTableRef.value?.clearSelection()
}

function toggleProjectRowSelection(row, _column, event) {
  if (event?.target?.closest?.('button, a, input, textarea, select, label, .el-checkbox, .el-radio, .el-switch')) return
  const selected = selectedProjects.value.includes(row)
  projectTableRef.value?.toggleRowSelection(row, !selected)
}

async function claimSelectedProjects() {
  const claimProjects = [...claimableSelectedProjects.value]
  if (!claimProjects.length) return
  try {
    await ElMessageBox.confirm(
      `确认自主承接这 ${claimProjects.length} 个未绑定项目的管理主负责人归属吗？`,
      '自主承接管理项目',
      { type: 'warning', confirmButtonText: '确认承接', cancelButtonText: '取消' }
    )
    claiming.value = true
    await claimManagementProjectsAPI(
      claimProjects
    )
    ElMessage.success(`已承接 ${claimProjects.length} 个管理项目`)
    clearProjectSelection()
    await loadData()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || error?.message || '自主承接管理项目失败')
    }
  } finally {
    claiming.value = false
  }
}

async function decideRequest(request, decision) {
  const isAccept = decision === 'accept'
  try {
    await ElMessageBox.confirm(
      isAccept
        ? `确认接收这 ${request.projects?.length || 0} 个项目的管理主负责人归属吗？`
        : '确认拒绝这次管理层项目交接吗？',
      isAccept ? '确认管理归属' : '拒绝管理归属',
      { type: isAccept ? 'warning' : 'error' }
    )
    const api = isAccept
      ? acceptProjectManagerHandoverAPI
      : rejectProjectManagerHandoverAPI
    await api(request.id, {})
    ElMessage.success(isAccept ? '已接收管理项目' : '已拒绝管理层交接')
    await loadData()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || error?.message || '处理管理层交接失败')
    }
  }
}

function handlePendingNotification() {
  loadData()
}

onMounted(() => {
  loadData()
  window.addEventListener('project-manager-handover-pending', handlePendingNotification)
})

onBeforeUnmount(() => {
  window.removeEventListener('project-manager-handover-pending', handlePendingNotification)
})
</script>

<style scoped>
.management-handover {
  margin-bottom: 10px;
}

.panel-title,
.request-header,
.request-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  margin: 8px 0 6px;
  font-size: 13px;
  font-weight: 600;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.incoming-list {
  margin-bottom: 10px;
}

.request-card {
  margin-bottom: 8px;
}

.request-header > div {
  display: flex;
  gap: 6px;
}

.request-time,
.request-note {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.request-note {
  margin-top: 8px;
}

.request-projects {
  margin-top: 10px;
}

.request-actions {
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.handover-form {
  margin-top: 18px;
}
</style>
