<template>
  <el-card class="translation-projects-page">
    <template #header>
      <div class="card-header">
        <span class="page-title">笔译项目流程</span>
        <div class="card-header__actions">
          <div class="entity-picker-trigger">
            <el-input
              :model-value="currentEntityDisplayText"
              readonly
              clearable
              placeholder="请选择母订单或子订单"
              class="entity-picker-input"
              @click="openEntityPicker"
              @clear="clearCurrentEntity"
            />
            <el-button type="primary" @click="openEntityPicker">选择订单</el-button>
          </div>
          <el-button
            v-if="canOpenProjectChat"
            class="chat-entry-button"
            type="primary"
            plain
            @click="openProjectChatDrawer"
          >
            项目沟通
          </el-button>
        </div>
      </div>
    </template>

    <el-steps
      :active="currentStepIndexInFlow"
      finish-status="success"
      process-status="process"
      align-center
      class="workflow-steps"
    >
      <el-step
        v-for="step in effectiveSteps"
        :key="step.key"
        :title="step.title"
        :description="step.role"
        :class="{ 'is-current-stage': step.key === workflowState.currentStageKey }"
      />
    </el-steps>

    <WorkflowStageCard
      ref="stageCardRef"
      :current-project="currentProject"
      :current-entity-type="currentEntityType"
      :current-sub-order="currentSubOrder"
      :workflow-state="workflowState"
      :current-stage="currentStage"
      :current-stage-editable-fields="currentStageEditableFields"
      :can-operate-current-stage="canOperateCurrentStage"
      :is-at-reception="isAtReception"
      :is-current-stage-done="isCurrentStageDone"
      :stage-note-for-current-stage="stageNoteForCurrentStage"
      :next-stage-after-reception="nextStageAfterReception"
      :next-stage-for-assignee="nextStageForAssignee"
      :next-stage-role-options="nextStageRoleOptions"
      :next-stage-users="nextStageUsers"
      :next-stage-users-loading="nextStageUsersLoading"
      :reception-assign-ready="receptionAssignReady"
      :transition-assign-ready="transitionAssignReady"
      :can-rollback-one="canRollbackOne"
      :can-rollback-two="canRollbackTwo"
      :can-rollback-to-start="canRollbackToStart"
      :resolve-field-value="resolveFieldValue"
      :difficulty-label="difficultyLabel"
      :ui-state="stageUiState"
      :stage-form-data="stageFormData"
      @save-progress="saveCurrentStageProgress"
      @confirm-difficulty="confirmDifficulty"
      @complete-stage="completeCurrentStage"
      @rollback="openRollbackDialog"
    />

    <el-empty v-if="!currentProject" class="empty-stage">
      <template #description>
        <p>请在上方输入框选择项目，或从下方「待我处理」Tab 中点「进入」。</p>
        <p class="empty-hint">若项目当前阶段为「客户专员」且尚未设定难度，选择后将显示难度评级与下一环节负责人。</p>
      </template>
    </el-empty>

    <el-dialog
      v-model="rollbackDialogVisible"
      :title="rollbackDialogTitle"
      width="480px"
      @close="handleRollbackDialogClose"
    >
      <p class="rollback-hint">请填写打回原因，便于上一环节负责人知悉并重新处理。该记录将保留在操作日志中。</p>
      <el-input
        v-model="rollbackNote"
        type="textarea"
        :rows="4"
        placeholder="请输入打回原因（必填）..."
        maxlength="300"
        show-word-limit
      />
      <template #footer>
        <el-button @click="rollbackDialogVisible = false">取消</el-button>
        <el-button type="warning" :disabled="!rollbackNote.trim()" @click="confirmRollback">
          确认打回
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="entityPickerVisible"
      title="选择订单"
      width="1120px"
      top="6vh"
      destroy-on-close
    >
      <div class="entity-picker-toolbar">
        <el-input
          v-model="entityPickerFilters.keyword"
          clearable
          placeholder="搜索订单号、项目名称"
          style="width: 260px"
          @keyup.enter="loadEntityPickerOptions"
        />
        <el-select v-model="entityPickerFilters.entityType" clearable placeholder="订单类型" style="width: 120px">
          <el-option label="母订单" value="project" />
          <el-option label="子订单" value="suborder" />
        </el-select>
        <el-input
          v-model="entityPickerFilters.clientShortName"
          clearable
          placeholder="客户简称"
          style="width: 140px"
        />
        <el-select v-model="entityPickerFilters.projectStatus" clearable placeholder="项目状态" style="width: 140px">
          <el-option
            v-for="status in pickerStatusOptions"
            :key="status.value"
            :label="status.label"
            :value="status.value"
          />
        </el-select>
        <el-select v-model="entityPickerFilters.dateType" placeholder="日期类型" style="width: 140px">
          <el-option label="创建时间" value="createdAt" />
          <el-option label="交稿时间" value="customerDeadlineTime" />
        </el-select>
        <el-date-picker
          v-model="entityPickerFilters.dateRange"
          type="daterange"
          unlink-panels
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
        <el-button type="primary" :loading="entityPickerLoading" @click="loadEntityPickerOptions">查询</el-button>
        <el-button @click="resetEntityPickerFilters">重置</el-button>
      </div>

      <el-alert
        type="info"
        :closable="false"
        class="entity-picker-tip"
        title="支持按订单号、项目名称快速搜索，也可以结合客户、项目状态和日期范围缩小范围。双击行可直接进入。"
      />

      <el-table
        ref="entityPickerTableRef"
        v-loading="entityPickerLoading"
        :data="entityPickerPagedRows"
        border
        highlight-current-row
        row-key="entityKey"
        class="entity-picker-table"
        @current-change="handleEntityPickerCurrentChange"
        @row-dblclick="confirmEntityPickerSelection"
      >
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row._type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
              {{ row._type === 'suborder' ? '子订单' : '母订单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="orderNoDisplay" label="订单号" width="180" />
        <el-table-column prop="projectNameDisplay" label="项目名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="clientShortName" label="客户简称" width="140" show-overflow-tooltip />
        <el-table-column label="项目状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusType(row.projectStatus)">
              {{ getStatusLabel(row.projectStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="customerDeadlineTime" label="交稿时间" width="180" />
        <el-table-column prop="createdAt" label="创建时间" width="180" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="selectEntityFromPicker(row)">选择</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="entity-picker-pagination">
        <el-pagination
          v-model:current-page="entityPickerPagination.page"
          v-model:page-size="entityPickerPagination.pageSize"
          background
          layout="total, sizes, prev, pager, next"
          :total="entityPickerTotal"
          :page-sizes="[10, 20, 50]"
        />
      </div>

      <template #footer>
        <el-button @click="entityPickerVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!entityPickerCurrentRow" @click="confirmEntityPickerSelection()">
          确认选择
        </el-button>
      </template>
    </el-dialog>

    <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
      <el-tab-pane label="待我处理" name="my_tasks">
        <MyTasksTab :tasks="myTaskList" :current-user-name="currentUserName" :stage-by-key="stageByKey" @select="onMyTaskRowClick" />
      </el-tab-pane>

      <el-tab-pane label="项目概览" name="overview">
        <el-descriptions v-if="currentProject" :column="2" border>
          <el-descriptions-item label="订单号">{{ currentProject.orderNo || currentProject.subOrderNo || currentProject.sub_order_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ currentProject.projectName || currentProject.subProjectName || currentProject.sub_project_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ currentProject.clientShortName || currentProject.client_short_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户编号">{{ currentProject.clientCode || currentProject.client_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">
            <el-tag :type="getStatusType(workflowState.projectStatus || currentProject.projectStatus || currentProject.project_status)" size="small">
              {{ getStatusLabel(workflowState.projectStatus || currentProject.projectStatus || currentProject.project_status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="难度评级">
            {{ workflowState.difficulty ? difficultyLabel(workflowState.difficulty) : '未设定' }}
          </el-descriptions-item>
          <el-descriptions-item label="客户交稿时间">{{ currentProject.customerDeadlineTime || currentProject.customer_deadline_time || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ currentProject.createdAt || currentProject.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="2">{{ currentProject.updatedAt || currentProject.updated_at || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="请先选择项目" />
      </el-tab-pane>

      <el-tab-pane label="项目文件" name="files">
        <ProjectFilesTab
          :project-id="fileProjectId"
          :order-no="fileOrderNo"
          :entity-type="currentEntityType"
          :active="activeTab === 'files'"
        />
      </el-tab-pane>

      <el-tab-pane label="翻译/审核进度" name="progress">
        <el-descriptions v-if="currentProject" :column="2" border>
          <el-descriptions-item label="译员安排">{{ currentProject.translatorAssignee || currentProject.translatorId || currentProject.translator_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="译员安排时间">{{ currentProject.translatorAssignmentTime || currentProject.translator_assignment_time || '-' }}</el-descriptions-item>
          <el-descriptions-item label="译员交稿进度">{{ currentProject.translatorDeliveryProgress || currentProject.translator_delivery_progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核 1 进度">{{ currentProject.review1Progress || currentProject.review1_progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核前专检进度">{{ currentProject.preReviewQcProgress || currentProject.pre_review_qc_progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="排版进度">{{ currentProject.layoutProgress || currentProject.layout_progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="整理进度">{{ currentProject.consolidationProgress || currentProject.consolidation_progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发客户时间">{{ currentProject.sentToClientTime || currentProject.sent_to_client_time || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核后专检进度">{{ currentProject.postReviewQcProgress || currentProject.post_review_qc_progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核 2 进度">{{ currentProject.review2Progress || currentProject.review2_progress || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="请先选择项目" />
      </el-tab-pane>

      <el-tab-pane label="日志记录" name="logs">
        <el-form :inline="true" :model="logFilters" size="small" class="log-filter-bar">
          <el-form-item label="类型">
            <el-select v-model="logFilters.direction" clearable placeholder="全部" style="width: 120px">
              <el-option label="推进" value="forward" />
              <el-option label="回退" value="rollback" />
            </el-select>
          </el-form-item>
          <el-form-item label="环节">
            <el-select v-model="logFilters.stage" clearable placeholder="全部" style="width: 180px">
              <el-option v-for="item in logStageOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="操作人">
            <el-select v-model="logFilters.operator" clearable placeholder="全部" style="width: 180px">
              <el-option v-for="item in logOperatorOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker
              v-model="logFilters.dateRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>
        </el-form>
        <el-timeline v-if="filteredTransitionLog.length" reverse>
          <el-timeline-item
            v-for="(entry, index) in filteredTransitionLog"
            :key="`${entry.at}-${index}`"
            :timestamp="entry.at"
            placement="top"
            :type="entry.direction === 'rollback' ? 'danger' : undefined"
          >
            <el-card shadow="never" :class="{ 'log-rollback': entry.direction === 'rollback' }">
              <p class="log-action">
                <el-tag v-if="entry.direction === 'rollback'" type="danger" size="small">回退</el-tag>
                <el-tag v-else type="success" size="small">推进</el-tag>
                {{ entry.description }}
              </p>
              <p v-if="entry.note" class="log-note">{{ entry.note }}</p>
              <p v-if="entry.nextAssigneeUserName" class="log-operator">下一负责人：{{ entry.nextAssigneeUserName }}</p>
              <p v-if="entry.operator" class="log-operator">操作人：{{ entry.operator }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无符合条件的日志记录" />
      </el-tab-pane>
    </el-tabs>

    <el-drawer
      v-model="chatDrawerVisible"
      class="project-chat-drawer"
      direction="rtl"
      size="560px"
      :modal="false"
      :lock-scroll="false"
      @close="handleChatDrawerClose"
    >
      <template #header>
        <div class="project-chat-drawer__header">
          <div class="project-chat-drawer__title">项目沟通</div>
          <div class="project-chat-drawer__subtitle">
            {{ currentProject?.orderNo || '-' }} · {{ currentProject?.projectName || '未选择母订单' }}
          </div>
        </div>
      </template>
      <ProjectChatPanel
        :project-id="currentProjectId"
        :active="chatDrawerVisible && currentEntityType === 'project'"
        :drawer-mode="true"
      />
    </el-drawer>
  </el-card>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import ProjectChatPanel from '@/components/ProjectChatPanel.vue'
import { getProject } from '@/api/projects'
import { getSubOrder } from '@/api/subOrders'
import { getStoredRoles } from '@/utils/permission'
import { useEntityPicker } from '@/composables/useEntityPicker'
import { buildPreviewEffectiveStages, difficultyLabel, getStatusLabel, getStatusType, useNextStageUsers, useWorkflow } from '@/composables/useWorkflow'
import MyTasksTab from './components/MyTasksTab.vue'
import ProjectFilesTab from './components/ProjectFilesTab.vue'
import WorkflowStageCard from './components/WorkflowStageCard.vue'

const route = useRoute()
const router = useRouter()

const projectList = ref([])
const mixedEntityList = ref([])
const selectedProjectRow = ref(null)

const currentProjectId = ref('')
const currentEntityType = ref('project')
const currentSubOrder = ref(null)
const currentEntityKey = ref('')
const activeTab = ref('my_tasks')
const chatDrawerVisible = ref(false)
const stageCardRef = ref(null)

const stageUiState = reactive({
  handoverNote: '',
  assignMode: 'personal',
  groupAssignRole: '',
  nextAssigneeUserId: '',
  pendingDifficulty: null,
  pendingFileEditable: null
})

const rollbackDialogVisible = ref(false)
const rollbackSteps = ref(1)
const rollbackToStart = ref(false)
const rollbackNote = ref('')
const stageFormData = reactive({})

const {
  myTaskList,
  stageByKey,
  stageDefinitions,
  stageProgressMap,
  loadMyTasks,
  loadWorkflowConfig,
  getWorkflowState,
  ensureWorkflowState,
  submitDifficulty,
  saveStageData,
  transitionStage,
  rollbackStage
} = useWorkflow()

const {
  pickerStatusOptions,
  entityPickerVisible,
  entityPickerLoading,
  entityPickerTableRef,
  entityPickerCurrentRow,
  entityPickerFilters,
  entityPickerPagination,
  entityPickerPagedRows,
  entityPickerTotal,
  buildEntityKey,
  getEntityDisplayText,
  loadMixedOptions,
  loadEntityPickerOptions,
  handleEntityPickerCurrentChange,
  resetEntityPickerFilters,
  openEntityPicker
} = useEntityPicker({
  currentEntityKey,
  currentEntityType,
  currentProjectId,
  currentSubOrder,
  selectedProjectRow,
  projectList,
  mixedEntityList
})

const workflowState = computed(() => getWorkflowState(currentEntityType.value, currentProjectId.value) || {})

const currentProject = computed(() => {
  if (currentEntityType.value === 'suborder') {
    return currentSubOrder.value || (currentProjectId.value ? { id: currentProjectId.value } : undefined)
  }
  if (selectedProjectRow.value) return selectedProjectRow.value
  if (!currentProjectId.value) return undefined
  return projectList.value.find((item) => String(item.id) === String(currentProjectId.value))
})

const currentEntityDisplayText = computed(() => {
  if (currentEntityType.value === 'suborder') {
    return getEntityDisplayText(currentSubOrder.value)
  }
  return getEntityDisplayText(currentProject.value ? { ...currentProject.value, _type: 'project' } : null)
})

const effectiveSteps = computed(() => {
  if (Array.isArray(workflowState.value.effectiveStages) && workflowState.value.effectiveStages.length) {
    return workflowState.value.effectiveStages
  }
  return buildPreviewEffectiveStages(workflowState.value.difficulty, workflowState.value.fileEditable, stageDefinitions.value)
})

const currentStage = computed(() => stageByKey.value[workflowState.value.currentStageKey] || null)

const currentStepIndexInFlow = computed(() => {
  const index = effectiveSteps.value.findIndex((item) => item.key === workflowState.value.currentStageKey)
  return index >= 0 ? index : 0
})

const isAtReception = computed(() => workflowState.value.currentStageKey === 'reception')

const isCurrentStageDone = computed(() => {
  const note = workflowState.value.stageNotes?.[workflowState.value.currentStageKey]
  return note !== undefined && note !== ''
})

const stageNoteForCurrentStage = computed(
  () => workflowState.value.stageNotes?.[workflowState.value.currentStageKey] ?? ''
)

const currentStageConfig = computed(
  () => stageProgressMap[workflowState.value.currentStageKey] || { editable: [], readonly: [] }
)

const currentStageEditableFields = computed(() => currentStageConfig.value.editable || [])
const transitionLog = computed(() => workflowState.value.transitionLog || [])

const logFilters = reactive({
  direction: '',
  stage: '',
  operator: '',
  dateRange: []
})

const logStageOptions = computed(() => {
  const seen = new Set()
  return transitionLog.value
    .flatMap((entry) => [entry.fromStage, entry.toStage])
    .filter((stage) => stage && !seen.has(stage) && seen.add(stage))
    .map((stage) => ({ value: stage, label: stageByKey.value[stage]?.title || stage }))
})

const logOperatorOptions = computed(() => {
  const seen = new Set()
  return transitionLog.value
    .map((entry) => entry.operator)
    .filter((name) => name && !seen.has(name) && seen.add(name))
})

const filteredTransitionLog = computed(() => transitionLog.value.filter((entry) => {
  if (logFilters.direction && entry.direction !== logFilters.direction) return false
  if (logFilters.stage && entry.fromStage !== logFilters.stage && entry.toStage !== logFilters.stage) return false
  if (logFilters.operator && entry.operator !== logFilters.operator) return false
  if (Array.isArray(logFilters.dateRange) && logFilters.dateRange.length === 2) {
    const [start, end] = logFilters.dateRange
    const entryDate = entry.at ? entry.at.slice(0, 10) : ''
    if (entryDate && (entryDate < start || entryDate > end)) return false
  }
  return true
}))

const canRollbackOne = computed(() => {
  const index = effectiveSteps.value.findIndex((item) => item.key === workflowState.value.currentStageKey)
  return index > 0
})

const canRollbackTwo = computed(() => {
  const index = effectiveSteps.value.findIndex((item) => item.key === workflowState.value.currentStageKey)
  return index >= 2
})

const canRollbackToStart = computed(() => {
  const index = effectiveSteps.value.findIndex((item) => item.key === workflowState.value.currentStageKey)
  return index >= 2
})

const rollbackDialogTitle = computed(() => (
  rollbackToStart.value ? '打回初始节点' : `打回 ${rollbackSteps.value} 个环节`
))

const currentUserName = computed(() => {
  try {
    return (localStorage.getItem('user_name') || '').trim() || '当前用户'
  } catch {
    return '当前用户'
  }
})

const currentUserId = computed(() => {
  try {
    return localStorage.getItem('user_id') || ''
  } catch {
    return ''
  }
})

const canOpenProjectChat = computed(() => currentEntityType.value === 'project' && !!currentProjectId.value)

const canOperateCurrentStage = computed(() => {
  const state = workflowState.value
  if (!state.currentStageKey) return false

  const roles = getStoredRoles()
  if (roles.includes('admin') || roles.includes('超级管理员')) return true
  if (state.currentStageKey === 'reception') {
    return roles.includes('客户专员') || roles.includes('项目经理')
  }
  if (roles.includes('项目经理')) return true
  if (state.groupAssignRole && !state.currentAssigneeUserId) {
    return roles.includes(state.groupAssignRole)
  }
  if (state.currentAssigneeUserId) {
    return String(state.currentAssigneeUserId) === String(currentUserId.value)
  }
  if (state.currentAssigneeUserName) {
    return state.currentAssigneeUserName === currentUserName.value
  }

  const stage = stageByKey.value[state.currentStageKey]
  if (!stage) return false
  if (Array.isArray(stage.assignRoles) && stage.assignRoles.length) {
    return stage.assignRoles.some((role) => roles.includes(role))
  }
  return roles.includes(stage.role)
})

const nextStageAfterReception = computed(() => {
  if (workflowState.value.currentStageKey !== 'reception') return null
  if (!stageUiState.pendingDifficulty || stageUiState.pendingFileEditable === null) return null
  const steps = buildPreviewEffectiveStages(stageUiState.pendingDifficulty, stageUiState.pendingFileEditable, stageDefinitions.value)
  return steps[1] || null
})

const nextStageForAssignee = computed(() => {
  if (!workflowState.value.currentStageKey || workflowState.value.currentStageKey === 'completed') return null
  const index = effectiveSteps.value.findIndex((item) => item.key === workflowState.value.currentStageKey)
  if (index < 0 || index >= effectiveSteps.value.length - 1) return null
  const next = effectiveSteps.value[index + 1]
  if (next?.key === 'completed') return null
  return next
})

const nextStageToAssign = computed(() => nextStageAfterReception.value || nextStageForAssignee.value)
const { nextStageUsers, nextStageUsersLoading } = useNextStageUsers(nextStageToAssign)

const nextStageRoleOptions = computed(() => {
  const stage = nextStageToAssign.value
  if (!stage) return []
  if (Array.isArray(stage.assignRoles) && stage.assignRoles.length) return stage.assignRoles
  if (stage.role && stage.role !== '-') return [stage.role]
  return []
})

const receptionAssignReady = computed(() => (
  stageUiState.assignMode === 'personal' ? !!stageUiState.nextAssigneeUserId : !!stageUiState.groupAssignRole
))

const transitionAssignReady = computed(() => (
  stageUiState.assignMode === 'personal' ? !!stageUiState.nextAssigneeUserId : !!stageUiState.groupAssignRole
))

const fileProjectId = computed(() => {
  if (currentEntityType.value === 'project') return currentProjectId.value
  return workflowState.value.translationProjectId || ''
})
const fileOrderNo = computed(() => {
  const parentProject = projectList.value.find(
    (item) => String(item.id) === String(fileProjectId.value)
  )
  return parentProject?.orderNo || parentProject?.order_no || ''
})

function resetStageActionState() {
  stageUiState.handoverNote = ''
  stageUiState.assignMode = 'personal'
  stageUiState.groupAssignRole = ''
  stageUiState.nextAssigneeUserId = ''
  stageUiState.pendingDifficulty = null
  stageUiState.pendingFileEditable = null
}

function resolveFieldValue(fieldKey) {
  const state = workflowState.value
  if (!state.stageData) return '-'

  const steps = state.effectiveStages?.length ? state.effectiveStages : effectiveSteps.value
  const currentIndex = steps.findIndex((item) => item.key === state.currentStageKey)
  for (let index = currentIndex; index >= 0; index -= 1) {
    const stageData = state.stageData[steps[index].key]
    if (stageData && stageData[fieldKey] !== undefined && stageData[fieldKey] !== '') {
      return stageData[fieldKey]
    }
  }

  return currentProject.value?.[fieldKey] ?? '-'
}

function initStageFormData() {
  const state = workflowState.value
  const config = stageProgressMap[state.currentStageKey]
  if (!config) return

  Object.keys(stageFormData).forEach((key) => delete stageFormData[key])

  const saved = state.stageData?.[state.currentStageKey]
  config.editable.forEach((field) => {
    stageFormData[field.key] = saved?.[field.key] ?? ''
  })

  if (state.currentStageKey !== 'reception' && state.currentStageKey !== 'completed' && stageFormData.projectStatus !== undefined) {
    stageFormData.projectStatus = stageFormData.projectStatus || 'in_progress'
  }
}

function formatDateTime(date) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function openRollbackDialog(steps, toStart = false) {
  rollbackSteps.value = steps
  rollbackToStart.value = !!toStart
  rollbackNote.value = ''
  rollbackDialogVisible.value = true
}

function handleRollbackDialogClose() {
  rollbackNote.value = ''
  rollbackSteps.value = 1
  rollbackToStart.value = false
}

function getRouteProjectId() {
  const value = route.query.projectId
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function getRouteSubOrderId() {
  const value = route.query.subOrderId
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function getRouteTab() {
  const value = route.query.tab
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function clearChatTabFromRoute() {
  if (getRouteTab() !== 'chat') return
  const nextQuery = { ...route.query }
  delete nextQuery.tab
  router.replace({ path: route.path, query: nextQuery }).catch(() => {})
}

function handleChatDrawerClose() {
  chatDrawerVisible.value = false
  clearChatTabFromRoute()
}

function openProjectChatDrawer() {
  if (canOpenProjectChat.value) {
    chatDrawerVisible.value = true
  }
}

function clearCurrentEntity() {
  currentEntityKey.value = ''
  onEntityKeyChange('')
}

async function ensureProjectLoaded(projectId) {
  if (!projectId) return

  const exists = projectList.value.some((item) => String(item.id) === String(projectId))
  if (exists) {
    selectedProjectRow.value = null
    return
  }

  try {
    const project = await getProject(String(projectId))
    if (!project?.id) return
    selectedProjectRow.value = project
    projectList.value = [
      project,
      ...projectList.value.filter((item) => String(item.id) !== String(project.id))
    ]
  } catch (error) {
    console.error('Failed to load selected project', error)
  }
}

async function ensureSubOrderLoaded(subOrderId) {
  if (!subOrderId) return
  const existing = mixedEntityList.value.find(
    (item) => item._type === 'suborder' && String(item.id) === String(subOrderId)
  )
  if (existing) {
    currentSubOrder.value = existing
    return
  }

  try {
    const subOrder = await getSubOrder(String(subOrderId))
    if (!subOrder?.id) return
    currentSubOrder.value = { ...subOrder, _type: 'suborder' }
  } catch (error) {
    console.error('加载指定子订单失败', error)
  }
}

async function fetchWorkflowState() {
  if (!currentProjectId.value) return

  try {
    if (currentEntityType.value === 'project') {
      await ensureProjectLoaded(currentProjectId.value)
    } else {
      await ensureSubOrderLoaded(currentProjectId.value)
    }
    await ensureWorkflowState(currentEntityType.value, currentProjectId.value)
    initStageFormData()
  } catch (error) {
    console.error('获取流程状态失败', error)
  }
}

function onProjectChange() {
  resetStageActionState()
  if (currentEntityType.value === 'suborder') {
    chatDrawerVisible.value = false
  }
  fetchWorkflowState()
}

function applyEntitySelection(entity) {
  if (!entity) {
    currentEntityType.value = 'project'
    currentProjectId.value = ''
    currentSubOrder.value = null
    selectedProjectRow.value = null
    currentEntityKey.value = ''
    onProjectChange()
    return
  }

  currentEntityKey.value = buildEntityKey(entity)
  if (entity._type === 'project') {
    currentEntityType.value = 'project'
    currentProjectId.value = entity.id
    currentSubOrder.value = null
    selectedProjectRow.value = entity
  } else {
    currentEntityType.value = 'suborder'
    currentProjectId.value = entity.id
    currentSubOrder.value = { ...entity }
    selectedProjectRow.value = null
    chatDrawerVisible.value = false
  }
  onProjectChange()
}

function selectEntityFromPicker(row) {
  entityPickerCurrentRow.value = row
  applyEntitySelection(row)
  entityPickerVisible.value = false
  activeTab.value = 'overview'
}

function confirmEntityPickerSelection(row = entityPickerCurrentRow.value) {
  if (row) {
    selectEntityFromPicker(row)
  }
}

function onEntityKeyChange(value) {
  if (!value) {
    applyEntitySelection(null)
    return
  }

  const [type, id] = value.split(':')
  if (type === 'project') {
    const project = projectList.value.find((item) => String(item.id) === id) || mixedEntityList.value.find((item) => item._type === 'project' && String(item.id) === id)
    applyEntitySelection({ ...(project || { id }), _type: 'project' })
    return
  }

  const subOrder = mixedEntityList.value.find((item) => item._type === 'suborder' && String(item.id) === id)
  applyEntitySelection(subOrder || { id, _type: 'suborder' })
}

function selectProject(projectIdOrRow) {
  if (projectIdOrRow && typeof projectIdOrRow === 'object' && 'id' in projectIdOrRow) {
    applyEntitySelection({ ...projectIdOrRow, _type: 'project' })
  } else {
    applyEntitySelection({ id: projectIdOrRow, _type: 'project' })
  }

  activeTab.value = 'overview'
  nextTick(() => {
    const element = stageCardRef.value?.$el ?? stageCardRef.value
    if (element?.scrollIntoView) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

function onMyTaskRowClick(row) {
  if (!row) return

  if (row.entity_type === 'suborder' && row.sub_order_id) {
    currentEntityType.value = 'suborder'
    currentSubOrder.value = {
      id: row.sub_order_id,
      subOrderNo: row.sub_order_no || row.order_no || ''
    }
    currentProjectId.value = row.sub_order_id
    currentEntityKey.value = `suborder:${row.sub_order_id}`
    selectedProjectRow.value = null
    activeTab.value = 'overview'
    onProjectChange()
    return
  }

  const projectId = row.translation_project_id || row.id
  currentEntityKey.value = `project:${projectId}`
  selectProject(projectId)
}

async function confirmDifficulty() {
  if (!workflowState.value.currentStageKey) return
  if (!stageUiState.pendingDifficulty || stageUiState.pendingFileEditable === null) return
  if (!receptionAssignReady.value || !canOperateCurrentStage.value) return

  const payload = {
    difficulty: stageUiState.pendingDifficulty,
    file_editable: stageUiState.pendingFileEditable,
    note: stageUiState.handoverNote?.trim() || '（无备注）',
    stage_data: { ...stageFormData }
  }

  if (stageUiState.assignMode === 'personal') {
    payload.next_assignee_id = stageUiState.nextAssigneeUserId
  } else {
    payload.group_assign_role = stageUiState.groupAssignRole
  }

  try {
    const isGroupAssign = stageUiState.assignMode === 'group'
    const assignedRole = payload.group_assign_role
    await submitDifficulty(currentEntityType.value, currentProjectId.value, payload)
    resetStageActionState()
    initStageFormData()
    ElMessage.success(
      isGroupAssign
        ? `难度已确认，已同组指派给「${assignedRole}」，流程已推进`
        : '难度已确认，已指定下一环节负责人，流程已推进'
    )
    loadProjects()
  } catch (error) {
    ElMessage.error(`操作失败：${error?.detail || error?.message || '请稍后重试'}`)
  }
}

async function saveCurrentStageProgress() {
  if (!workflowState.value.currentStageKey || !canOperateCurrentStage.value) return

  try {
    await saveStageData(currentEntityType.value, currentProjectId.value, {
      stage_data: { ...stageFormData }
    })
    ElMessage.success('本阶段进度已更新（暂存）')
  } catch (error) {
    ElMessage.error(`暂存数据失败：${error?.detail || error?.message || '请稍后重试'}`)
  }
}

async function completeCurrentStage() {
  if (!workflowState.value.currentStageKey || !canOperateCurrentStage.value) return

  const currentIndex = effectiveSteps.value.findIndex((item) => item.key === workflowState.value.currentStageKey)
  if (currentIndex < 0) return

  const nextStage = effectiveSteps.value[currentIndex + 1] || null
  if (nextStage && nextStage.key !== 'completed' && !transitionAssignReady.value) return

  const currentStageData = { ...stageFormData }
  if (currentStageData.actualTime === undefined || currentStageData.actualTime === '') {
    currentStageData.actualTime = formatDateTime(new Date())
  }

  const payload = {
    note: stageUiState.handoverNote?.trim() || '（无备注）',
    stage_data: currentStageData
  }

  if (nextStage && nextStage.key !== 'completed') {
    if (stageUiState.assignMode === 'personal') {
      payload.next_assignee_id = stageUiState.nextAssigneeUserId
    } else {
      payload.group_assign_role = stageUiState.groupAssignRole
    }
  }

  try {
    const isGroupAssign = stageUiState.assignMode === 'group'
    const assignedRole = payload.group_assign_role
    await transitionStage(currentEntityType.value, currentProjectId.value, payload)
    resetStageActionState()
    initStageFormData()
    ElMessage.success(
      nextStage && nextStage.key !== 'completed'
        ? (isGroupAssign
          ? `本阶段已完成，已同组指派给「${assignedRole}」，流程已推进`
          : '本阶段已完成，已指定下一环节负责人，流程已推进')
        : '本阶段已完成'
    )
    loadProjects()
  } catch (error) {
    ElMessage.error(`操作失败：${error?.detail || error?.message || '请稍后重试'}`)
  }
}

async function confirmRollback() {
  const note = rollbackNote.value?.trim()
  if (!note || !workflowState.value.currentStageKey) return

  try {
    await rollbackStage(currentEntityType.value, currentProjectId.value, {
      steps: rollbackSteps.value,
      to_start: rollbackToStart.value,
      note
    })
    rollbackDialogVisible.value = false
    handleRollbackDialogClose()
    resetStageActionState()
    initStageFormData()
    ElMessage.success(currentEntityType.value === 'suborder' ? '已成功打回子订单' : '已成功打回项目')
    loadProjects()
  } catch (error) {
    ElMessage.error(`操作失败：${error?.detail || error?.message || '请稍后重试'}`)
  }
}

async function loadProjects() {
  try {
    await loadWorkflowConfig()
    await loadMyTasks()
    await loadMixedOptions()

    const routeProjectId = getRouteProjectId()
    const routeSubOrderId = getRouteSubOrderId()
    if (routeProjectId || routeSubOrderId) return

    if (currentProjectId.value) {
      if (currentEntityType.value === 'project') {
        await ensureProjectLoaded(currentProjectId.value)
      }
      return
    }

    if (projectList.value.length) {
      const firstProject = projectList.value[0]
      currentEntityType.value = 'project'
      currentProjectId.value = firstProject.id
      currentEntityKey.value = `project:${firstProject.id}`
      selectedProjectRow.value = firstProject
      await fetchWorkflowState()
    }
  } catch (error) {
    console.error('加载流程页数据失败', error)
  }
}

watch(
  () => stageFormData.projectStatus,
  (value) => {
    if (!value || workflowState.value.currentStageKey === 'completed') return
    workflowState.value.projectStatus = value
  }
)

watch(
  () => stageUiState.assignMode,
  (mode) => {
    if (mode === 'personal') {
      stageUiState.groupAssignRole = ''
      return
    }
    stageUiState.nextAssigneeUserId = ''
    if (nextStageRoleOptions.value.length && !stageUiState.groupAssignRole) {
      stageUiState.groupAssignRole = nextStageRoleOptions.value[0]
    }
  }
)

watch(
  () => nextStageToAssign.value?.key,
  () => {
    stageUiState.nextAssigneeUserId = ''
    stageUiState.groupAssignRole = ''
    stageUiState.assignMode = 'personal'
  }
)

watch(
  () => [
    nextStageToAssign.value?.key || '',
    nextStageUsersLoading.value ? 'loading' : 'ready',
    nextStageUsers.value.map((user) => `${user.id}:${user.is_on_leave ? 1 : 0}`).join('|'),
    (workflowState.value.roleAssignments || workflowState.value.role_assignments || [])
      .map((item) => `${item.roleCode || item.role_code}:${item.assigneeId || item.assignee_id || ''}`)
      .join('|')
  ],
  () => {
    const stage = nextStageToAssign.value
    if (!stage || nextStageUsersLoading.value) return
    if (stageUiState.nextAssigneeUserId || stageUiState.groupAssignRole) return

    const roleCode = stage.roleCode || stage.role_code
    const assignments = workflowState.value.roleAssignments || workflowState.value.role_assignments || []
    const assignment = assignments.find((item) => (item.roleCode || item.role_code) === roleCode)
    const assigneeId = assignment?.assigneeId || assignment?.assignee_id || ''
    const configuredUser = nextStageUsers.value.find((user) => String(user.id) === String(assigneeId))
    if (configuredUser && !configuredUser.is_on_leave) {
      stageUiState.assignMode = 'personal'
      stageUiState.nextAssigneeUserId = configuredUser.id
      return
    }

    stageUiState.assignMode = 'group'
    stageUiState.groupAssignRole = nextStageRoleOptions.value[0] || ''
  },
  { immediate: true }
)

watch(
  () => [
    entityPickerFilters.keyword,
    entityPickerFilters.entityType,
    entityPickerFilters.clientShortName,
    entityPickerFilters.projectStatus,
    entityPickerFilters.dateType,
    Array.isArray(entityPickerFilters.dateRange) ? entityPickerFilters.dateRange.join('|') : ''
  ],
  () => {
    entityPickerPagination.page = 1
  }
)

watch(
  () => entityPickerPagination.pageSize,
  () => {
    entityPickerPagination.page = 1
  }
)

watch(
  () => [entityPickerVisible.value, entityPickerPagedRows.value.length, entityPickerCurrentRow.value?.entityKey],
  async ([visible]) => {
    if (!visible || !entityPickerCurrentRow.value) return
    await nextTick()
    entityPickerTableRef.value?.setCurrentRow?.(entityPickerCurrentRow.value)
  }
)

watch(
  () => [route.query.projectId, route.query.subOrderId, route.query.tab],
  async () => {
    const routeProjectId = getRouteProjectId()
    const routeSubOrderId = getRouteSubOrderId()
    chatDrawerVisible.value = getRouteTab() === 'chat'
    if (routeSubOrderId) {
      const subOrderChanged = currentEntityType.value !== 'suborder'
        || String(currentProjectId.value || '') !== String(routeSubOrderId)
      if (!subOrderChanged) return

      currentEntityType.value = 'suborder'
      currentProjectId.value = routeSubOrderId
      currentSubOrder.value = { id: routeSubOrderId, _type: 'suborder' }
      currentEntityKey.value = `suborder:${routeSubOrderId}`
      selectedProjectRow.value = null
      activeTab.value = 'overview'
      resetStageActionState()
      await fetchWorkflowState()
      return
    }

    if (!routeProjectId) return

    const projectChanged = currentEntityType.value !== 'project' || String(currentProjectId.value || '') !== String(routeProjectId)
    if (!projectChanged) return

    currentEntityType.value = 'project'
    currentProjectId.value = routeProjectId
    currentSubOrder.value = null
    currentEntityKey.value = `project:${routeProjectId}`
    selectedProjectRow.value = null
    activeTab.value = 'overview'
    resetStageActionState()
    await fetchWorkflowState()
  },
  { immediate: true }
)

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.translation-projects-page {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}

.card-header__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-left: auto;
}

.entity-picker-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: min(100%, 560px);
}

.entity-picker-input {
  min-width: 320px;
}

.entity-picker-input :deep(.el-input__wrapper) {
  cursor: pointer;
}

.chat-entry-button {
  flex-shrink: 0;
}

.workflow-steps {
  margin-bottom: 24px;
}

.workflow-steps :deep(.el-step.is-current-stage .el-step__head .el-step__icon) {
  background: var(--el-color-warning-light-7);
  border-color: var(--el-color-warning);
  color: var(--el-color-warning-dark-2);
}

.workflow-steps :deep(.el-step.is-current-stage .el-step__title) {
  color: var(--el-color-warning-dark-2);
  font-weight: 700;
}

.empty-stage {
  margin: 40px 0;
}

.empty-stage .empty-hint {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.rollback-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px 0;
}

.detail-tabs {
  margin-top: 8px;
}

.entity-picker-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.entity-picker-tip {
  margin-bottom: 12px;
}

.entity-picker-table {
  margin-bottom: 16px;
}

.entity-picker-pagination {
  display: flex;
  justify-content: flex-end;
}

.project-chat-drawer :deep(.el-drawer__header) {
  margin-bottom: 8px;
}

.project-chat-drawer :deep(.el-drawer__body) {
  padding-top: 0;
}

.project-chat-drawer__title {
  font-size: 16px;
  font-weight: 600;
}

.project-chat-drawer__subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.log-filter-bar {
  margin-bottom: 12px;
}

.log-action {
  margin: 0 0 4px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-note {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 6px 0 0 0;
  padding: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
}

.log-operator {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
}

.log-rollback {
  border-left: 3px solid var(--el-color-danger);
}
</style>
