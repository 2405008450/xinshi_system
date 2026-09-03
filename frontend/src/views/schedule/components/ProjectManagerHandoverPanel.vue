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
          <el-table-column prop="order_no" :label="WORKBENCH_FIELD_LABELS.orderNo" width="145" show-overflow-tooltip />
          <el-table-column :label="WORKBENCH_FIELD_LABELS.projectType" :width="WORKBENCH_COLUMN_WIDTHS.projectType">
            <template #default="{ row }">{{ row.project_type_label || '笔译项目' }}</template>
          </el-table-column>
          <el-table-column :label="WORKBENCH_FIELD_LABELS.projectTask" min-width="170">
            <template #default="{ row }"><WorkbenchProjectTaskCell :row="row" /></template>
          </el-table-column>
          <el-table-column prop="client_short_name" :label="WORKBENCH_FIELD_LABELS.client" width="100" show-overflow-tooltip />
          <el-table-column :label="WORKBENCH_FIELD_LABELS.projectNode" width="168">
            <template #default="{ row }">
              <DeadlineHintCell :deadline="row.customer_deadline_time" :status="row.project_status" />
            </template>
          </el-table-column>
          <el-table-column :label="WORKBENCH_FIELD_LABELS.projectStatus" width="132">
            <template #default="{ row }">
              <ProjectStatusSwitch
                :project-type="resolveProjectType(row)"
                :project-id="resolveProjectId(row)"
                :status="row.project_status"
              />
            </template>
          </el-table-column>
          <el-table-column :label="WORKBENCH_FIELD_LABELS.languageDirection" width="105">
            <template #default="{ row }"><LanguagePairText :value="row.language_pair" /></template>
          </el-table-column>
        </el-table>
        <div class="request-actions">
          <el-button size="small" type="danger" plain @click="decideRequest(request, 'reject')">拒绝</el-button>
          <el-button size="small" type="primary" @click="decideRequest(request, 'accept')">确认接收</el-button>
        </div>
      </el-card>
    </div>

    <div class="panel-title">
      <span>我负责及可承接的管理项目（{{ projects.length }}）</span>
      <div class="panel-actions">
        <el-button
          v-if="canSelfClaim"
          type="primary"
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

    <AppForm :inline="true" :model="filterDraft" class="workbench-search-form">
      <el-form-item label="关键词">
        <el-input v-model="filterDraft.project" clearable placeholder="项目、任务或订单号" class="workbench-search-input" @input="onTextFilterInput" @keyup.enter="applyFilters" @clear="applyFilters" />
      </el-form-item>
      <el-form-item label="客户">
        <el-input v-model="filterDraft.client" clearable placeholder="客户全称或简称" class="workbench-client-input" @input="onTextFilterInput" @keyup.enter="applyFilters" @clear="applyFilters" />
      </el-form-item>
      <el-form-item label="项目状态">
        <el-select v-model="filterDraft.project_statuses" multiple collapse-tags :max-collapse-tags="1" clearable placeholder="全部状态" class="workbench-status-select" @change="applyFilters">
          <el-option v-for="option in projectStatusFilterOptions" :key="option.value" :label="`${option.label}（${option.count}）`" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item class="workbench-search-actions">
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advancedFilterVisible" :count="advancedFilterCount" popper-class="workbench-management-advanced-filter" @clear="clearAdvancedFilters" @reset="resetFilters">
          <AppForm :model="filterDraft" label-width="100px" class="workbench-advanced-form">
            <el-row :gutter="16">
              <el-col :xs="24" :md="12">
                <el-form-item label="项目类型">
                  <el-select v-model="filterDraft.project_types" multiple clearable placeholder="全部类型" style="width: 100%" @change="applyFilters">
                    <el-option v-for="option in WORKBENCH_PROJECT_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="当前负责人">
                  <el-select v-model="filterDraft.assignees" multiple clearable collapse-tags filterable placeholder="全部负责人" style="width: 100%" @change="applyFilters">
                    <el-option v-for="option in assigneeFilterOptions" :key="option.value" :label="`${option.label}（${option.count}）`" :value="option.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="管理归属">
                  <el-select v-model="filterDraft.managers" multiple clearable collapse-tags filterable placeholder="全部归属" style="width: 100%" @change="applyFilters">
                    <el-option v-for="option in managerFilterOptions" :key="option.value" :label="`${option.label}（${option.count}）`" :value="option.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="语言方向">
                  <el-input v-model="filterDraft.language_pair" clearable placeholder="按语言方向筛选" @input="onTextFilterInput" @keyup.enter="applyFilters" @clear="applyFilters" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="风险状态">
                  <el-select v-model="filterDraft.risk_states" multiple clearable placeholder="全部风险" style="width: 100%" @change="applyFilters">
                    <el-option label="已逾期" value="overdue" />
                    <el-option label="24 小时内到期" value="urgent" />
                    <el-option label="正常" value="normal" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </AppForm>
        </AdvancedFilterPopover>
      </el-form-item>
    </AppForm>

    <div class="management-list-toolbar">
      <span>筛选结果 {{ filteredProjects.length }} 条</span>
      <el-pagination
        v-if="filteredProjects.length"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZE_OPTIONS"
        :total="filteredProjects.length"
        layout="total, sizes, prev, pager, next"
        size="small"
        background
        @current-change="handleProjectPageChange"
        @size-change="handleProjectPageSizeChange"
      />
    </div>

    <el-table
      ref="projectTableRef"
      v-loading="loading"
      :data="pagedProjects"
      border
      size="small"
      class="workbench-data-table row-click-select-table"
      :row-key="row => `${row.project_type || 'translation'}:${row.project_id || row.translation_project_id}`"
      @selection-change="selectedProjects = $event"
      @row-click="toggleProjectRowSelection"
    >
      <template #empty>
        <span>{{ projects.length ? '没有符合当前筛选条件的管理项目' : '暂无负责或可承接的管理项目' }}</span>
      </template>
      <el-table-column type="selection" :width="WORKBENCH_COLUMN_WIDTHS.selection" />
      <el-table-column
        type="index"
        label="序号"
        :width="WORKBENCH_COLUMN_WIDTHS.index"
        :index="getProjectIndex"
      />
      <el-table-column prop="order_no" :label="WORKBENCH_FIELD_LABELS.orderNo" :width="WORKBENCH_COLUMN_WIDTHS.orderNo" show-overflow-tooltip />
      <el-table-column :label="WORKBENCH_FIELD_LABELS.projectType" :width="WORKBENCH_COLUMN_WIDTHS.projectType">
        <template #default="{ row }"><el-tag type="info" size="small" effect="plain">{{ row.project_type_label || '笔译项目' }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="WORKBENCH_FIELD_LABELS.projectTask" :width="WORKBENCH_COLUMN_WIDTHS.projectTask">
        <template #default="{ row }">
          <WorkbenchProjectTaskCell :row="row" />
        </template>
      </el-table-column>
      <el-table-column prop="client_short_name" :label="WORKBENCH_FIELD_LABELS.client" :width="WORKBENCH_COLUMN_WIDTHS.client" show-overflow-tooltip>
      </el-table-column>
      <el-table-column :label="WORKBENCH_FIELD_LABELS.projectNode" :width="WORKBENCH_COLUMN_WIDTHS.customerDeadline">
        <template #default="{ row }">
          <DeadlineHintCell :deadline="row.customer_deadline_time" :status="row.project_status" />
        </template>
      </el-table-column>
      <el-table-column :label="WORKBENCH_FIELD_LABELS.projectStatus" :width="WORKBENCH_COLUMN_WIDTHS.projectStatus">
        <template #default="{ row }">
          <ProjectStatusSwitch
            :project-type="resolveProjectType(row)"
            :project-id="resolveProjectId(row)"
            :status="row.project_status"
            :writable="canWriteProjects"
            @updated="handleProjectStatusUpdated"
          />
        </template>
      </el-table-column>
      <el-table-column :label="WORKBENCH_FIELD_LABELS.languageDirection" :width="WORKBENCH_COLUMN_WIDTHS.languagePair">
        <template #default="{ row }"><LanguagePairText :value="row.language_pair" /></template>
      </el-table-column>
      <el-table-column prop="current_assignee_name" :label="WORKBENCH_FIELD_LABELS.currentAssignee" :width="WORKBENCH_COLUMN_WIDTHS.currentAssignee">
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
      <el-table-column prop="project_manager_name" :label="WORKBENCH_FIELD_LABELS.managementOwnership" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.project_manager_id" type="success" size="small" effect="plain">
            {{ row.project_manager_name || '已绑定' }}
          </el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">未绑定·可承接</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="WORKBENCH_FIELD_LABELS.operation" width="150" fixed="right" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click.stop="$emit('open-project', row)">进入项目</el-button>
          <el-button v-if="canRecordProgress(row)" type="primary" link size="small" @click.stop="openProgressDialog(row)">记录进展</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="filteredProjects.length" class="management-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZE_OPTIONS"
        :total="filteredProjects.length"
        layout="total, sizes, prev, pager, next, jumper"
        size="small"
        background
        @current-change="handleProjectPageChange"
        @size-change="handleProjectPageSizeChange"
      />
    </div>
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
      <AppForm label-width="100px" class="handover-form">
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
      </AppForm>
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
      <AppForm label-width="90px">
        <el-form-item label="项目"><el-input :model-value="progressProject?.project_name || progressProject?.order_no" disabled /></el-form-item>
        <el-form-item label="工作日期" required><el-date-picker v-model="progressForm.work_date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="进展内容" required><el-input v-model="progressForm.progress_content" type="textarea" :rows="4" maxlength="10000" show-word-limit /></el-form-item>
        <el-form-item label="耗时（分钟）"><el-input-number v-model="progressForm.duration_minutes" :min="0" :max="1440" style="width: 100%" /></el-form-item>
        <el-form-item label="工作结果"><el-input v-model="progressForm.result_content" type="textarea" :rows="2" maxlength="10000" show-word-limit /></el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="progressVisible = false">取消</el-button>
        <el-button type="primary" :loading="progressSubmitting" @click="submitProgress">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
import { hasRole, hasPermission } from '@/utils/permission'
import { createWorkEntry } from '@/api/tasks'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import LanguagePairText from '@/components/common/LanguagePairText.vue'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import ProjectStatusSwitch from '@/components/common/ProjectStatusSwitch.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import { WORKBENCH_COLUMN_WIDTHS } from '@/constants/workbenchColumns'
import {
  WORKBENCH_FIELD_LABELS,
  WORKBENCH_PROJECT_TYPE_LABELS,
  WORKBENCH_PROJECT_TYPE_OPTIONS,
  WORKBENCH_PROJECT_TYPE_VALUES
} from '@/constants/workbenchFields'
import {
  getProjectStatusLabel,
  normalizeProjectStatus,
  resolveProjectId,
  resolveProjectType
} from '@/utils/projectStatus'
import { getWorkItemDeadlineState } from '@/utils/workItemDeadline'
import {
  WORKBENCH_PAGE_SIZE_OPTIONS,
  clearWorkbenchFilterKeys,
  countActiveWorkbenchFilterGroups,
  getWorkbenchFilterStorageKey,
  getWorkbenchLastPage,
  matchesWorkbenchFilterGroups,
  paginateWorkbenchRows,
} from '@/utils/workbenchList'
import ProjectRoleAssigneesPopover from './ProjectRoleAssigneesPopover.vue'
import WorkbenchProjectTaskCell from './WorkbenchProjectTaskCell.vue'

const emit = defineEmits(['updated', 'open-project', 'visible-count-change'])
const canWriteProjects = hasPermission('projects:write')

async function handleProjectStatusUpdated(payload) {
  const projectId = String(payload?.projectId || '')
  if (projectId) {
    projects.value.forEach((item) => {
      if (String(resolveProjectId(item)) === projectId) item.project_status = payload.status
    })
  }
  await loadData()
  emit('updated')
}
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
    ElMessage.error(getLocalizedErrorMessage(error, '记录进展失败'))
  } finally {
    progressSubmitting.value = false
  }
}
const selectedProjects = ref([])
const handoverProjects = ref([])
const projectTableRef = ref(null)
const currentPage = ref(1)
const pageSize = ref(10)
const PAGE_SIZE_OPTIONS = WORKBENCH_PAGE_SIZE_OPTIONS
const loading = ref(false)
const submitting = ref(false)
const claiming = ref(false)
const dialogVisible = ref(false)
const targetManagerId = ref('')
const reason = ref('')
const note = ref('')
const canSelfClaim = hasRole('项目经理')
const advancedFilterVisible = ref(false)

const FILTER_STORAGE_KEY = getWorkbenchFilterStorageKey('management-projects', currentUserId)

function projectStatusFilterKey(row) {
  const projectType = resolveProjectType(row)
  return `${projectType}:${normalizeProjectStatus(projectType, row?.project_status)}`
}

function personFilterKey(id, name, emptyKey) {
  if (id) return `user:${id}`
  if (name) return `name:${name}`
  return emptyKey
}

function readStoredFilters() {
  const fallback = {
    project_types: [], project_statuses: [], assignees: [], managers: [],
    risk_states: [], project: '', client: '', language_pair: ''
  }
  try {
    const parsed = JSON.parse(localStorage.getItem(FILTER_STORAGE_KEY) || 'null')
    if (!parsed || typeof parsed !== 'object') return fallback
    return {
      project_types: Array.isArray(parsed.project_types) ? parsed.project_types.filter(value => WORKBENCH_PROJECT_TYPE_VALUES.includes(value)) : [],
      project_statuses: Array.isArray(parsed.project_statuses) ? parsed.project_statuses.filter(value => typeof value === 'string' && value.includes(':')) : [],
      assignees: Array.isArray(parsed.assignees) ? parsed.assignees.filter(value => typeof value === 'string') : [],
      managers: Array.isArray(parsed.managers) ? parsed.managers.filter(value => typeof value === 'string') : [],
      risk_states: Array.isArray(parsed.risk_states) ? parsed.risk_states.filter(value => ['overdue', 'urgent', 'normal'].includes(value)) : [],
      project: typeof parsed.project === 'string' ? parsed.project : '',
      client: typeof parsed.client === 'string' ? parsed.client : '',
      language_pair: typeof parsed.language_pair === 'string' ? parsed.language_pair : ''
    }
  } catch {
    localStorage.removeItem(FILTER_STORAGE_KEY)
    return fallback
  }
}

const filters = reactive(readStoredFilters())
const filterDraft = reactive({
  ...filters,
  project_types: [...filters.project_types],
  project_statuses: [...filters.project_statuses],
  assignees: [...filters.assignees],
  managers: [...filters.managers],
  risk_states: [...filters.risk_states],
})
const advancedFilterCount = computed(() => countActiveWorkbenchFilterGroups(
  filterDraft,
  ['project_types', 'assignees', 'managers', 'language_pair', 'risk_states'],
))
let filterDebounceTimer = null

function copyDraftToAppliedFilters() {
  filters.project_types = [...filterDraft.project_types]
  filters.project_statuses = [...filterDraft.project_statuses]
  filters.assignees = [...filterDraft.assignees]
  filters.managers = [...filterDraft.managers]
  filters.risk_states = [...filterDraft.risk_states]
  filters.project = filterDraft.project.trim()
  filters.client = filterDraft.client.trim()
  filters.language_pair = filterDraft.language_pair.trim()
}

function applyFilters() {
  clearTimeout(filterDebounceTimer)
  filterDebounceTimer = null
  copyDraftToAppliedFilters()
  currentPage.value = 1
  clearProjectSelection()
}

function onTextFilterInput(value) {
  clearTimeout(filterDebounceTimer)
  filterDebounceTimer = null
  if (!String(value || '').trim()) {
    applyFilters()
    return
  }
  filterDebounceTimer = setTimeout(applyFilters, 400)
}

function resetFilters() {
  clearWorkbenchFilterKeys(filterDraft, [
    'project_types', 'project_statuses', 'assignees', 'managers', 'risk_states',
    'project', 'client', 'language_pair',
  ])
  advancedFilterVisible.value = false
  applyFilters()
}

function clearAdvancedFilters() {
  clearWorkbenchFilterKeys(filterDraft, [
    'project_types', 'assignees', 'managers', 'risk_states', 'language_pair',
  ])
  applyFilters()
}

function buildPersonOptions(idField, nameField, emptyKey, emptyLabel) {
  const options = new Map()
  projects.value.forEach((row) => {
    const value = personFilterKey(row[idField], row[nameField], emptyKey)
    const existing = options.get(value)
    if (existing) {
      existing.count += 1
    } else {
      options.set(value, { value, label: value === emptyKey ? emptyLabel : (row[nameField] || '未知人员'), count: 1 })
    }
  })
  return Array.from(options.values()).sort((left, right) => {
    if (left.value === emptyKey) return 1
    if (right.value === emptyKey) return -1
    return left.label.localeCompare(right.label, 'zh-CN')
  })
}

const assigneeFilterOptions = computed(() => buildPersonOptions(
  'current_assignee_id', 'current_assignee_name', 'unassigned', '待认领（角色池）'
))
const managerFilterOptions = computed(() => buildPersonOptions(
  'project_manager_id', 'project_manager_name', 'unbound', '未绑定·可承接'
))
const projectStatusFilterOptions = computed(() => {
  const options = new Map()
  projects.value.forEach((row) => {
    const projectType = resolveProjectType(row)
    const status = normalizeProjectStatus(projectType, row.project_status)
    if (!status) return
    const value = projectStatusFilterKey(row)
    const existing = options.get(value)
    if (existing) existing.count += 1
    else options.set(value, {
      value,
      label: `${WORKBENCH_PROJECT_TYPE_LABELS[projectType] || '项目'} · ${getProjectStatusLabel(projectType, status)}`,
      count: 1
    })
  })
  return Array.from(options.values()).sort((left, right) => left.label.localeCompare(right.label, 'zh-CN'))
})

const filteredProjects = computed(() => {
  return projects.value.filter(row => matchesWorkbenchFilterGroups(row, filters, {
    textFields: {
      project: ['project_name', 'task_type', 'order_no'],
      client: ['client_name', 'client_short_name'],
      language_pair: ['language_pair'],
    },
    multiValueGetters: {
      project_types: resolveProjectType,
      project_statuses: projectStatusFilterKey,
      assignees: item => personFilterKey(item.current_assignee_id, item.current_assignee_name, 'unassigned'),
      managers: item => personFilterKey(item.project_manager_id, item.project_manager_name, 'unbound'),
      risk_states: getWorkItemDeadlineState,
    },
  }))
})

const pagedProjects = computed(() => {
  return paginateWorkbenchRows(filteredProjects.value, currentPage.value, pageSize.value)
})

function getProjectIndex(index) {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

function handleProjectPageChange() {
  clearProjectSelection()
}

function handleProjectPageSizeChange() {
  currentPage.value = 1
  clearProjectSelection()
}

watch(filters, (value) => {
  currentPage.value = 1
  clearProjectSelection()
  try {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(value))
  } catch {}
})

watch(() => filteredProjects.value.length, (total) => {
  const lastPage = getWorkbenchLastPage(total, pageSize.value)
  if (currentPage.value > lastPage) currentPage.value = lastPage
}, { immediate: true })

watch(() => projects.value.length, (total) => {
  emit('visible-count-change', total)
}, { immediate: true })
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
    ElMessage.error(getLocalizedErrorMessage(error, '加载管理层项目交接失败'))
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
    ElMessage.error(getLocalizedErrorMessage(error, '加载项目经理列表失败'))
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
    ElMessage.error(getLocalizedErrorMessage(error, '发起管理层项目交接失败'))
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
  if (event?.target?.closest?.('button, a, input, textarea, select, label, .el-checkbox, .el-radio, .el-switch, .el-dropdown, .project-status-switch')) return
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
      ElMessage.error(getLocalizedErrorMessage(error, '自主承接管理项目失败'))
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
      ElMessage.error(getLocalizedErrorMessage(error, '处理管理层交接失败'))
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
  clearTimeout(filterDebounceTimer)
  window.removeEventListener('project-manager-handover-pending', handlePendingNotification)
})
</script>

<style scoped>
.management-handover {
  margin-bottom: 4px;
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

.workbench-search-form {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 8px;
  padding: 10px 12px 2px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-extra-light);
}

.workbench-search-form :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: 8px;
}

.workbench-search-input { width: 240px; }
.workbench-client-input { width: 190px; }
.workbench-status-select { width: 210px; }
.workbench-search-actions { margin-left: auto; }
.workbench-advanced-form :deep(.el-form-item) { margin-bottom: 12px; }

.management-list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.management-pagination {
  display: flex;
  justify-content: flex-end;
  margin: 8px 0 12px;
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

@media (max-width: 900px) {
  .panel-title,
  .management-list-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .panel-actions {
    flex-wrap: wrap;
  }

  .workbench-search-form {
    display: grid;
    padding: 10px 10px 2px;
  }

  .workbench-search-input,
  .workbench-client-input,
  .workbench-status-select {
    width: 100%;
  }

  .workbench-search-actions { margin-left: 0; }

  .management-list-toolbar {
    overflow-x: auto;
  }
}
</style>
