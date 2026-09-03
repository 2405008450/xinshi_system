<template>
  <div class="unified-tasks-panel">
    <el-radio-group v-model="sourceFilter" size="small" class="source-filter">
      <el-radio-button value="all">全部（{{ visibleTaskCount }}）</el-radio-button>
      <el-radio-button value="project">项目任务（{{ projectVisibleCount }}）</el-radio-button>
      <el-radio-button value="non_project">非项目任务（{{ filteredNonProjectItems.length }}）</el-radio-button>
    </el-radio-group>

    <section v-show="sourceFilter !== 'non_project'">
      <div v-if="sourceFilter === 'all'" class="subsection-title">项目任务</div>
      <MyTasksPanel
        :current-user-name="currentUserName"
        :tasks-list="projectItems"
        @visible-count-change="projectVisibleCount = $event"
        @open-chat="$emit('open-chat', $event)"
        @open-project="$emit('open-project', $event)"
        @open-manuscript="$emit('open-manuscript', $event)"
        @record-work="openWorkEntry"
        @refresh="$emit('refresh')"
      />
    </section>

    <section v-if="sourceFilter !== 'project'" class="non-project-section">
      <div class="non-project-toolbar">
        <div v-if="sourceFilter === 'all'" class="subsection-title">非项目任务</div>
        <div class="toolbar-actions">
          <el-select v-model="nonProjectStatusFilter" size="small" style="width: 120px">
            <el-option label="进行中" value="open" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="全部状态" value="all" />
          </el-select>
          <el-input
            v-model="keyword"
            size="small"
            clearable
            placeholder="搜索任务名称、类型或安排人"
            style="width: 220px"
          />
          <el-button size="small" plain @click="openRecurrenceDialog">周期任务</el-button>
          <el-button size="small" type="primary" @click="openCreateTask(false)">添加个人任务</el-button>
          <el-button v-if="canAssign" size="small" type="success" plain @click="openCreateTask(true)">分配非项目任务</el-button>
        </div>
      </div>

      <el-table
        v-if="filteredNonProjectItems.length"
        :data="filteredNonProjectItems"
        border
        size="small"
        class="workbench-data-table non-project-table"
        :row-class-name="nonProjectRowClassName"
      >
        <el-table-column prop="task_type" label="任务类型" width="120" />
        <el-table-column prop="task_name" label="任务名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="assigner_name" label="安排人" width="120" />
        <el-table-column prop="assignee_name" label="负责人" width="120" />
        <el-table-column label="安排时间" width="165">
          <template #default="{ row }">{{ formatDateTime(row.assigned_at) }}</template>
        </el-table-column>
        <el-table-column label="预定完成时间" width="168">
          <template #default="{ row }">
            <DeadlineHintCell :deadline="row.planned_completion_at" :status="row.status" mode="task" />
          </template>
        </el-table-column>
        <el-table-column label="实际完成时间" width="165">
          <template #default="{ row }">{{ formatDateTime(row.actual_completion_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="STATUS_TYPE[row.status] || 'info'" size="small">
              {{ STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="255" fixed="right">
          <template #default="{ row }">
            <el-button v-if="hasAction(row, 'start')" type="primary" link size="small" @click="runAction(row, 'start')">开始</el-button>
            <el-button v-if="hasAction(row, 'work_entry')" type="success" link size="small" @click="openWorkEntry(row)">记进展</el-button>
            <el-button v-if="hasAction(row, 'complete')" type="success" link size="small" @click="runAction(row, 'complete')">完成</el-button>
            <el-button v-if="hasAction(row, 'reopen')" type="warning" link size="small" @click="runAction(row, 'reopen')">重新打开</el-button>
            <el-button v-if="hasAction(row, 'edit')" type="primary" link size="small" @click="openEditTask(row)">编辑</el-button>
            <el-button v-if="hasAction(row, 'cancel')" type="danger" link size="small" @click="runAction(row, 'cancel')">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else class="compact-empty" description="暂无非项目任务" :image-size="56" />
    </section>

    <el-dialog v-model="taskDialogVisible" :title="taskDialogTitle" width="640px" destroy-on-close>
      <AppForm ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="110px">
        <el-form-item label="任务类型" prop="task_type">
          <el-select v-model="taskForm.task_type" style="width: 100%">
            <el-option v-for="type in TASK_TYPES" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="taskForm.task_type === '自定义'" label="自定义类型" required>
          <el-input
            v-model="taskForm.custom_task_type"
            maxlength="50"
            show-word-limit
            placeholder="请输入具体任务类型"
          />
        </el-form-item>
        <el-form-item label="任务名称" prop="task_name">
          <el-input v-model="taskForm.task_name" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item v-if="assigning || (editingTask && canAssign)" label="负责人" prop="assignee_id">
          <el-select v-model="taskForm.assignee_id" filterable style="width: 100%">
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="user.is_on_leave ? `${user.full_name || user.username}（请假至 ${formatDateTime(user.leave_end)}）` : (user.full_name || user.username)"
              :value="user.id"
              :disabled="user.is_on_leave"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="负责人">
          <el-input :model-value="currentDisplayName" readonly />
        </el-form-item>
        <el-form-item label="安排人">
          <el-input :model-value="taskAssignerDisplay" readonly />
        </el-form-item>
        <el-form-item label="安排时间">
          <el-input :model-value="taskAssignedAtDisplay" readonly />
        </el-form-item>
        <el-form-item v-if="!editingTask" label="任务周期">
          <el-select v-model="taskForm.frequency" style="width: 100%">
            <el-option label="一次性" value="once" />
            <el-option label="每日" value="daily" />
            <el-option label="工作日" value="workday" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
          </el-select>
        </el-form-item>
        <template v-if="!editingTask && taskForm.frequency !== 'once'">
          <el-form-item label="开始日期">
            <el-date-picker v-model="taskForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="taskForm.end_date" type="date" value-format="YYYY-MM-DD" clearable style="width: 100%" />
          </el-form-item>
          <el-form-item label="默认截止时间">
            <el-time-picker v-model="taskForm.default_due_time" format="HH:mm" value-format="HH:mm:ss" clearable style="width: 100%" />
          </el-form-item>
        </template>
        <el-form-item v-else label="预定完成时间">
          <el-date-picker
            v-model="taskForm.planned_completion_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            clearable
            style="width: 100%"
            format="YYYY-MM-DD HH:mm"
            time-format="HH:mm"
            :show-now="true"
            :show-confirm="true"
            :show-footer="true"
          />
        </el-form-item>
        <el-form-item label="实际完成时间">
          <el-input :model-value="taskActualCompletionDisplay" readonly />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="taskForm.remark" type="textarea" :rows="3" maxlength="5000" show-word-limit />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskSubmitting" @click="submitTask">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="recurrenceVisible" title="周期任务管理" width="900px" destroy-on-close>
      <el-table v-loading="recurrenceLoading" :data="recurrences" border size="small">
        <el-table-column prop="task_type" label="任务类型" width="120" />
        <el-table-column prop="task_name" label="任务名称" min-width="220" />
        <el-table-column label="周期" width="100">
          <template #default="{ row }">{{ FREQUENCY_LABEL[row.frequency] || row.frequency }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120">
          <template #default="{ row }">{{ row.end_date || '长期' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '暂停' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="toggleRecurrence(row)">
              {{ row.is_active ? '暂停' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="workEntryVisible" title="记录今日进展" width="620px" destroy-on-close>
      <AppForm ref="workEntryFormRef" :model="workEntryForm" :rules="workEntryRules" label-width="110px">
        <el-form-item label="关联任务">
          <el-input :model-value="activeWorkItem?.task_name || activeWorkItem?.project_name" disabled />
        </el-form-item>
        <el-form-item label="工作日期" prop="work_date">
          <el-date-picker v-model="workEntryForm.work_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="工作进展" prop="progress_content">
          <el-input v-model="workEntryForm.progress_content" type="textarea" :rows="3" maxlength="10000" show-word-limit />
        </el-form-item>
        <el-form-item label="耗时（分钟）" prop="duration_minutes">
          <el-input-number v-model="workEntryForm.duration_minutes" :min="0" :max="1440" controls-position="right" />
        </el-form-item>
        <el-form-item label="工作成果">
          <el-input v-model="workEntryForm.result_content" type="textarea" :rows="2" maxlength="10000" show-word-limit />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="workEntryVisible = false">取消</el-button>
        <el-button type="primary" :loading="workEntrySubmitting" @click="submitWorkEntry">保存进展</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import MyTasksPanel from './MyTasksPanel.vue'
import { getUsers } from '@/api/users'
import {
  changeNonProjectTaskStatus,
  createNonProjectTask,
  createTaskRecurrence,
  createWorkEntry,
  getTaskRecurrences,
  setTaskRecurrenceActive,
  updateNonProjectTask
} from '@/api/tasks'
import { hasRole, isSuperAdmin } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { DEADLINE_STATE, compareWorkItemsByDeadline, getWorkItemDeadlineState } from '@/utils/workItemDeadline'

const props = defineProps({
  currentUserName: { type: String, default: '' },
  currentUserId: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  referenceDate: { type: String, default: '' }
})
const emit = defineEmits(['open-chat', 'open-project', 'open-manuscript', 'refresh'])

const TASK_TYPES = ['非项目工作', '自定义']
const FREQUENCY_LABEL = { daily: '每日', workday: '工作日', weekly: '每周', monthly: '每月' }
const STATUS_LABEL = { pending: '待处理', in_progress: '进行中', completed: '已完成', cancelled: '已取消' }
const STATUS_TYPE = { pending: 'info', in_progress: 'primary', completed: 'success', cancelled: 'danger' }

const sourceFilter = ref('all')
const projectVisibleCount = ref(0)
const keyword = ref('')
const nonProjectStatusFilter = ref('open')
const canAssign = computed(() => isSuperAdmin() || hasRole('项目经理'))
const projectItems = computed(() => props.items.filter(item => item.source_type === 'project'))
const nonProjectItems = computed(() => props.items.filter(item => item.source_type === 'non_project'))
const personalNonProjectItems = computed(() => nonProjectItems.value.filter(item => (
  !props.currentUserId || String(item.assignee_id || '') === props.currentUserId
)))
const filteredNonProjectItems = computed(() => {
  const statusFilter = nonProjectStatusFilter.value
  const value = keyword.value.trim().toLowerCase()
  const list = personalNonProjectItems.value.filter(item => {
    const statusMatches = statusFilter === 'all'
      || (statusFilter === 'open' && ['pending', 'in_progress'].includes(item.status))
      || item.status === statusFilter
    if (!statusMatches) return false
    if (!value) return true
    return [item.task_type, item.task_name, item.assigner_name, item.assignee_name, item.remark]
      .some(field => String(field || '').toLowerCase().includes(value))
  })
  const now = new Date()
  return list.sort((a, b) => compareWorkItemsByDeadline(a, b, now))
})
const visibleTaskCount = computed(() => projectVisibleCount.value + filteredNonProjectItems.value.length)

const deadlineState = getWorkItemDeadlineState

function nonProjectRowClassName({ row }) {
  const state = deadlineState(row)
  if (state === DEADLINE_STATE.OVERDUE) return 'overdue-row'
  if (state === DEADLINE_STATE.URGENT) return 'urgent-row'
  return ''
}

function hasAction(row, action) {
  return Array.isArray(row.available_actions) && row.available_actions.includes(action)
}

const users = ref([])
const taskDialogVisible = ref(false)
const taskSubmitting = ref(false)
const assigning = ref(false)
const editingTask = ref(null)
const taskFormRef = ref(null)
const taskForm = reactive({
  task_type: '非项目工作',
  custom_task_type: '',
  task_name: '',
  assignee_id: '',
  planned_completion_at: '',
  remark: '',
  frequency: 'once',
  start_date: '',
  end_date: '',
  default_due_time: ''
})
const taskRules = {
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
  task_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  assignee_id: [{ required: true, message: '请选择负责人', trigger: 'change' }]
}
const taskDialogTitle = computed(() => editingTask.value ? '编辑非项目任务' : (assigning.value ? '分配非项目任务' : '添加个人任务'))
const currentDisplayName = computed(() => {
  try {
    return localStorage.getItem('user_full_name') || props.currentUserName || '当前登录用户'
  } catch {
    return props.currentUserName || '当前登录用户'
  }
})
const taskAssignerDisplay = computed(() =>
  editingTask.value?.assigner_name || currentDisplayName.value
)
const taskAssignedAtDisplay = computed(() =>
  editingTask.value?.assigned_at
    ? formatDateTime(editingTask.value.assigned_at)
    : '保存后自动记录当前时间'
)
const taskActualCompletionDisplay = computed(() =>
  editingTask.value?.actual_completion_at
    ? formatDateTime(editingTask.value.actual_completion_at)
    : '任务完成后自动记录'
)

function todayString() {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function resetTaskForm() {
  Object.assign(taskForm, {
    task_type: '非项目工作',
    custom_task_type: '',
    task_name: '',
    assignee_id: '',
    planned_completion_at: '',
    remark: '',
    frequency: 'once',
    start_date: todayString(),
    end_date: '',
    default_due_time: ''
  })
}

async function loadUsers() {
  if (!canAssign.value || users.value.length) return
  try {
    users.value = (await getUsers({ limit: 500, include_leave_status: true })).filter(user => user.is_active)
  } catch (error) {
    ElMessage.error(error?.detail || '加载用户失败')
  }
}

function openCreateTask(isAssigning) {
  resetTaskForm()
  editingTask.value = null
  assigning.value = isAssigning
  if (isAssigning) loadUsers()
  taskDialogVisible.value = true
}

function openEditTask(row) {
  resetTaskForm()
  editingTask.value = row
  assigning.value = false
  const isPresetType = TASK_TYPES.includes(row.task_type) && row.task_type !== '自定义'
  Object.assign(taskForm, {
    task_type: isPresetType ? row.task_type : '自定义',
    custom_task_type: isPresetType ? '' : row.task_type,
    task_name: row.task_name,
    assignee_id: row.assignee_id || '',
    planned_completion_at: row.planned_completion_at ? String(row.planned_completion_at).slice(0, 19) : '',
    remark: row.remark || ''
  })
  if (canAssign.value) loadUsers()
  taskDialogVisible.value = true
}

async function submitTask() {
  try {
    await taskFormRef.value?.validate()
  } catch {
    return
  }
  const effectiveTaskType = taskForm.task_type === '自定义'
    ? taskForm.custom_task_type.trim()
    : taskForm.task_type
  if (!effectiveTaskType) {
    ElMessage.warning('请输入自定义任务类型')
    return
  }
  taskSubmitting.value = true
  try {
    const common = {
      task_type: effectiveTaskType,
      task_name: taskForm.task_name,
      assignee_id: taskForm.assignee_id || undefined,
      remark: taskForm.remark || undefined
    }
    if (editingTask.value) {
      await updateNonProjectTask(editingTask.value.source_id, {
        ...common,
        planned_completion_at: taskForm.planned_completion_at || null
      })
    } else if (taskForm.frequency === 'once') {
      await createNonProjectTask({
        ...common,
        planned_completion_at: taskForm.planned_completion_at || null
      })
    } else {
      await createTaskRecurrence({
        ...common,
        frequency: taskForm.frequency,
        start_date: taskForm.start_date,
        end_date: taskForm.end_date || null,
        default_due_time: taskForm.default_due_time || null
      })
    }
    ElMessage.success('任务已保存')
    taskDialogVisible.value = false
    emit('refresh')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '保存任务失败'))
  } finally {
    taskSubmitting.value = false
  }
}

async function runAction(row, action) {
  const actionText = { start: '开始', complete: '完成', reopen: '重新打开', cancel: '取消' }[action]
  try {
    if (action !== 'start') {
      await ElMessageBox.confirm(`确定要${actionText}任务“${row.task_name}”吗？`, '任务操作', { type: 'warning' })
    }
    await changeNonProjectTaskStatus(row.source_id, action)
    ElMessage.success(`任务已${actionText}`)
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getLocalizedErrorMessage(error, '任务操作失败'))
    }
  }
}

const recurrenceVisible = ref(false)
const recurrenceLoading = ref(false)
const recurrences = ref([])

async function loadRecurrences() {
  recurrenceLoading.value = true
  try {
    recurrences.value = await getTaskRecurrences()
  } catch (error) {
    recurrences.value = []
    ElMessage.error(error?.detail || '加载周期任务失败')
  } finally {
    recurrenceLoading.value = false
  }
}

function openRecurrenceDialog() {
  recurrenceVisible.value = true
  loadRecurrences()
}

async function toggleRecurrence(row) {
  try {
    await setTaskRecurrenceActive(row.id, !row.is_active)
    ElMessage.success(row.is_active ? '周期任务已暂停' : '周期任务已启用')
    await loadRecurrences()
  } catch (error) {
    ElMessage.error(error?.detail || '修改周期任务失败')
  }
}

const workEntryVisible = ref(false)
const workEntrySubmitting = ref(false)
const workEntryFormRef = ref(null)
const activeWorkItem = ref(null)
const workEntryForm = reactive({
  work_date: '',
  progress_content: '',
  duration_minutes: 0,
  result_content: ''
})
const workEntryRules = {
  work_date: [{ required: true, message: '请选择工作日期', trigger: 'change' }],
  progress_content: [{ required: true, message: '请填写工作进展', trigger: 'blur' }]
}

function openWorkEntry(row) {
  activeWorkItem.value = row
  Object.assign(workEntryForm, {
    work_date: props.referenceDate || todayString(),
    progress_content: '',
    duration_minutes: 0,
    result_content: ''
  })
  workEntryVisible.value = true
}

async function submitWorkEntry() {
  try {
    await workEntryFormRef.value?.validate()
  } catch {
    return
  }
  workEntrySubmitting.value = true
  try {
    const source = activeWorkItem.value.source_type === 'project'
      ? (activeWorkItem.value.project_responsibility_id
          ? { project_responsibility_id: activeWorkItem.value.project_responsibility_id }
          : { workflow_instance_id: activeWorkItem.value.workflow_instance_id || activeWorkItem.value.source_id })
      : { non_project_task_id: activeWorkItem.value.source_id }
    await createWorkEntry({ ...workEntryForm, ...source })
    ElMessage.success('工作进展已记录')
    workEntryVisible.value = false
    emit('refresh')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '保存进展失败'))
  } finally {
    workEntrySubmitting.value = false
  }
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.unified-tasks-panel {
  position: relative;
}

.source-filter { margin-bottom: 8px; }
.subsection-title { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); margin-bottom: 8px; }

@media (min-width: 1280px) {
  .unified-tasks-panel :deep(.task-toolbar) {
    position: absolute;
    top: 0;
    right: 0;
    margin-bottom: 0;
  }
}
.non-project-section { margin-top: 4px; }
.non-project-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.toolbar-actions { display: flex; align-items: center; gap: 6px; margin-left: auto; flex-wrap: wrap; justify-content: flex-end; }
.compact-empty { padding: 12px 0 8px; }
.compact-empty :deep(.el-empty__description) { margin-top: 6px; }
.non-project-table :deep(.overdue-row),
.non-project-table :deep(.overdue-row td) { background-color: var(--el-color-danger-light-9) !important; }
.non-project-table :deep(.overdue-row:hover),
.non-project-table :deep(.overdue-row:hover td) { background-color: var(--el-color-danger-light-8) !important; }
.non-project-table :deep(.urgent-row),
.non-project-table :deep(.urgent-row td) { background-color: var(--el-color-warning-light-9) !important; }
.non-project-table :deep(.urgent-row:hover),
.non-project-table :deep(.urgent-row:hover td) { background-color: var(--el-color-warning-light-8) !important; }

@media (max-width: 900px) {
  .non-project-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar-actions {
    width: 100%;
    margin-left: 0;
    justify-content: flex-start;
  }
}
</style>
