<template>
  <!--
    流程说明：
    - 完整流程：客户专员 → 项目经理 → 项目专员 → 项目助理 → 译员 → 译审 → 完成
    - 难度由客户专员在接稿时初步判断，决定是否跳过环节：
      · 简单：跳过 项目经理、译审
      · 普通：跳过 译审
      · 复杂：全流程
    - 支持打回上一环节/上两环节，打回原因与时间线、操作日志均保留
  -->
  <el-card class="translation-projects-page">
    <template #header>
      <div class="card-header">
        <span class="page-title">项目流程</span>
        <el-select
          v-model="currentProjectId"
          placeholder="选择项目（选后可在下方设定难度并推进流程）"
          filterable
          clearable
          style="width: 380px"
          @change="onProjectChange"
        >
          <el-option
            v-for="p in projectList"
            :key="p.id"
            :label="`${p.orderNo} · ${p.projectName}`"
            :value="p.id"
          />
        </el-select>
      </div>
    </template>

    <!-- 流程步骤条（按难度只显示有效环节） -->
    <el-steps :active="currentStepIndexInFlow" finish-status="success" align-center class="workflow-steps">
      <el-step
        v-for="(step, index) in effectiveSteps"
        :key="step.key"
        :title="step.title"
        :description="step.role"
      />
    </el-steps>

    <!-- 当前阶段操作区（客户专员在此设定难度并指定下一环节负责人） -->
    <el-card v-if="currentProject" ref="stageCardRef" class="stage-card" shadow="never">
      <template #header>
        <div class="stage-card-header">
          <span class="stage-name">当前阶段：{{ currentStage?.title }}</span>
          <el-tag type="primary" effect="plain">{{ currentStage?.role }}</el-tag>
          <el-tag v-if="workflowState.currentAssigneeUserName" type="success" effect="plain" class="assignee-tag">
            当前负责人：{{ workflowState.currentAssigneeUserName }}
          </el-tag>
          <el-tag v-if="workflowState.difficulty" type="info" effect="plain" class="difficulty-tag">
            难度：{{ difficultyLabel(workflowState.difficulty) }}
          </el-tag>
        </div>
      </template>

      <!-- 接稿且未设定难度：先选难度 -->
      <div v-if="isAtReception && !workflowState.difficulty" class="stage-difficulty">
        <div class="section-label">来稿难度评级（客户专员初步判断）</div>
        <p class="handover-hint">请根据来稿情况选择难度，将决定后续流程是否经过「项目经理」「译审」环节。</p>
        <el-radio-group v-model="pendingDifficulty" class="difficulty-radio">
          <el-radio label="simple">简单（跳过项目经理、译审）</el-radio>
          <el-radio label="normal">普通（跳过译审）</el-radio>
          <el-radio label="complex">复杂（全流程）</el-radio>
        </el-radio-group>
        <template v-if="nextStageAfterReception">
          <div class="section-label">下一环节负责人</div>
          <p class="handover-hint">指定由哪位同事处理下一环节「{{ nextStageAfterReception.title }}」。</p>
          <el-select
            v-model="nextAssigneeUserId"
            placeholder="请选择下一环节负责人"
            filterable
            clearable
            style="width: 100%; margin-bottom: 12px"
            :loading="nextStageUsersLoading"
          >
            <el-option
              v-for="u in nextStageUsers"
              :key="u.id"
              :label="u.full_name || u.username || u.id"
              :value="u.id"
            />
          </el-select>
        </template>
        <div class="stage-actions">
          <p v-if="!pendingDifficulty || !nextAssigneeUserId" class="action-hint">
            请先选择难度，再选择下一环节负责人后即可点击下方按钮提交。
          </p>
          <el-button type="primary" :disabled="!pendingDifficulty || !nextAssigneeUserId" @click="confirmDifficulty">
            确认难度并进入下一环节
          </el-button>
        </div>
      </div>

      <template v-else>
        <!-- 关键进度信息（只读） -->
        <div class="stage-progress">
          <div class="section-label">关键进度信息</div>
          <el-descriptions :column="2" border size="small">
            <template v-for="item in currentStageProgressFields" :key="item.key">
              <el-descriptions-item :label="item.label" :span="item.span ?? 1">
                <span class="readonly-value">{{ projectProgress[item.key] ?? '-' }}</span>
              </el-descriptions-item>
            </template>
          </el-descriptions>
        </div>

        <!-- 未完成：处理备注 / 交接留言 + 下一环节负责人 + 完成并提交 -->
        <div v-if="!isCurrentStageDone" class="stage-handover">
          <div class="section-label">处理备注 / 交接留言</div>
          <p class="handover-hint">向下一阶段负责人传递关键信息，提交后将推进流程并锁定本阶段备注。</p>
          <el-input
            v-model="handoverNote"
            type="textarea"
            :rows="4"
            placeholder="请输入本阶段处理说明、注意事项或交接给下一阶段的留言..."
            maxlength="500"
            show-word-limit
          />
          <template v-if="nextStageForAssignee">
            <div class="section-label">下一环节负责人</div>
            <p class="handover-hint">指定由哪位同事处理下一环节「{{ nextStageForAssignee.title }}」。</p>
            <el-select
              v-model="nextAssigneeUserId"
              placeholder="请选择下一环节负责人"
              filterable
              clearable
              style="width: 100%; margin-bottom: 12px"
              :loading="nextStageUsersLoading"
            >
              <el-option
                v-for="u in nextStageUsers"
                :key="u.id"
                :label="u.full_name || u.username || u.id"
                :value="u.id"
              />
            </el-select>
          </template>
          <div class="stage-actions stage-actions-multi">
            <el-button type="primary" :disabled="!!nextStageForAssignee && !nextAssigneeUserId" @click="completeCurrentStage">
              完成本阶段并提交
            </el-button>
            <el-button
              v-if="canRollbackOne"
              type="warning"
              plain
              @click="openRollbackDialog(1)"
            >
              打回上一环节
            </el-button>
            <el-button
              v-if="canRollbackTwo"
              type="warning"
              plain
              @click="openRollbackDialog(2)"
            >
              打回上两环节
            </el-button>
          </div>
        </div>

        <!-- 已完成：该阶段交接留言只读 -->
        <div v-else class="stage-handover-readonly">
          <div class="section-label">本阶段交接留言</div>
          <div class="readonly-note">{{ stageNoteForCurrentStage || '（无）' }}</div>
          <div v-if="canRollbackOne || canRollbackTwo" class="stage-actions" style="margin-top: 12px">
            <el-button v-if="canRollbackOne" type="warning" plain @click="openRollbackDialog(1)">
              打回上一环节
            </el-button>
            <el-button v-if="canRollbackTwo" type="warning" plain @click="openRollbackDialog(2)">
              打回上两环节
            </el-button>
          </div>
        </div>
      </template>
    </el-card>

    <el-empty v-else class="empty-stage">
      <template #description>
        <p>请在上方下拉框<strong>选择项目</strong>，或从下方「待我处理」Tab 中点「进入」。</p>
        <p class="empty-hint">若项目当前阶段为「客户专员」且尚未设定难度，选择后将显示<strong>难度评级</strong>与下一环节负责人。</p>
      </template>
    </el-empty>

    <!-- 打回原因弹窗 -->
    <el-dialog
      v-model="rollbackDialogVisible"
      :title="`打回${rollbackSteps}环节`"
      width="480px"
      @close="rollbackNote = ''"
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

    <!-- 下方 Tabs -->
    <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
      <el-tab-pane label="待我处理" name="my_tasks">
        <div class="section-label">当前登录用户「{{ currentUserName }}」待处理的笔译项目</div>
        <el-table :data="myTaskProjects" border size="small" highlight-current-row @current-change="onMyTaskRowClick">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="orderNo" label="订单号" width="140" />
          <el-table-column prop="projectName" label="项目名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="clientShortName" label="客户简称" width="120" />
          <el-table-column label="当前阶段" width="180">
            <template #default="{ row }">
              <span v-if="getWorkflowState(row.id)?.currentStageKey">
                {{ stageByKey[getWorkflowState(row.id).currentStageKey]?.title || getWorkflowState(row.id).currentStageKey }}
                <el-tag v-if="getWorkflowState(row.id).currentStageKey === 'reception' && !getWorkflowState(row.id).difficulty" type="warning" size="small" style="margin-left: 6px">待设定难度</el-tag>
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="selectProject(row)">进入</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!myTaskProjects.length" description="暂无待您处理的项目" />
      </el-tab-pane>

      <el-tab-pane label="项目概览" name="overview">
        <el-descriptions v-if="currentProject" :column="2" border>
          <el-descriptions-item label="订单号">{{ currentProject.orderNo }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ currentProject.projectName }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ currentProject.clientShortName }}</el-descriptions-item>
          <el-descriptions-item label="客户编号">{{ currentProject.clientCode }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">
            <el-tag :type="getStatusType(currentProject.projectStatus)" size="small">
              {{ getStatusLabel(currentProject.projectStatus) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="难度评级">
            {{ workflowState.difficulty ? difficultyLabel(workflowState.difficulty) : '未设定' }}
          </el-descriptions-item>
          <el-descriptions-item label="客户交稿时间">{{ currentProject.customerDeadlineTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ currentProject.createdAt || '-' }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="2">{{ currentProject.updatedAt || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="请先选择项目" />
      </el-tab-pane>

      <el-tab-pane label="文件管理" name="files">
        <el-table :data="fileList" border size="small" style="width: 100%">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="name" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="updatedAt" label="更新时间" width="160" />
        </el-table>
        <el-empty v-if="!fileList.length" description="暂无文件（接口未实现）" />
      </el-tab-pane>

      <el-tab-pane label="翻译/审核进度" name="progress">
        <el-descriptions v-if="currentProject" :column="2" border>
          <el-descriptions-item label="译员安排">{{ currentProject.translatorAssignee || '-' }}</el-descriptions-item>
          <el-descriptions-item label="译员安排时间">{{ currentProject.translatorAssignmentTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="译员交稿进度">{{ currentProject.translatorDeliveryProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核1进度">{{ currentProject.review1Progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核前专检进度">{{ currentProject.preReviewQcProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="排版进度">{{ currentProject.layoutProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="整理进度">{{ currentProject.consolidationProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发客户时间">{{ currentProject.sentToClientTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核后专检进度">{{ currentProject.postReviewQcProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核2进度">{{ currentProject.review2Progress || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="请先选择项目" />
      </el-tab-pane>

      <el-tab-pane label="操作日志" name="logs">
        <el-timeline v-if="transitionLog.length" reverse>
          <el-timeline-item
            v-for="(entry, i) in transitionLog"
            :key="i"
            :timestamp="entry.at"
            placement="top"
            :type="entry.direction === 'rollback' ? 'danger' : undefined"
          >
            <el-card shadow="never" :class="{ 'log-rollback': entry.direction === 'rollback' }">
              <p class="log-action">
                <el-tag v-if="entry.direction === 'rollback'" type="danger" size="small">打回</el-tag>
                <el-tag v-else type="success" size="small">推进</el-tag>
                {{ entry.description }}
              </p>
              <p v-if="entry.note" class="log-note">{{ entry.note }}</p>
              <p v-if="entry.nextAssigneeUserName" class="log-operator">指定下一环节负责人：{{ entry.nextAssigneeUserName }}</p>
              <p v-else-if="entry.operator" class="log-operator">{{ entry.operator }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无操作记录" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
/**
 * 流程状态与交接字段设计（便于与后端对齐）
 * ----------------------------------------
 * workflowState 单项目流程状态：
 *   - difficulty: 'simple'|'normal'|'complex'
 *   - currentStageKey: 当前环节 key（reception / project_manager / ... / completed）
 *   - currentAssigneeUserId: 当前环节负责人 user_id（UUID 或字符串）
 *   - currentAssigneeUserName: 当前环节负责人显示名（full_name 或 username）
 *   - stageNotes: { [stageKey]: string } 各环节交接留言
 *   - transitionLog: 操作日志数组，每项：
 *       at, fromStage, toStage, toTitle, direction('forward'|'rollback'),
 *       description, note?, operator?,
 *       nextAssigneeUserId?, nextAssigneeUserName?  // 推进时下一环节指定用户
 *
 * 完成并提交时：必填「下一环节负责人」nextAssigneeUserId，提交后写入 state 与 log。
 * 待我处理：筛选 currentAssigneeUserName === 当前登录用户 且 currentStageKey !== 'completed'。
 */
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjects } from '@/api/projects'
import { getUsersByRoleName } from '@/api/workflow'
import { getStoredRoles } from '@/utils/permission'
import { isMockEnabled } from '@/mock'

// ---------- 全流程阶段定义（顺序固定） ----------
const ALL_STAGES = [
  { key: 'reception', title: '客户专员', role: '客户专员' },
  { key: 'project_manager', title: '项目经理', role: '项目经理' },
  { key: 'project_specialist', title: '项目专员', role: '项目专员' },
  { key: 'project_assistant', title: '项目助理', role: '项目助理' },
  { key: 'translator', title: '译员', role: '译员' },
  { key: 'review', title: '译审', role: '译审' },
  { key: 'completed', title: '完成', role: '-' }
]

const STAGE_KEYS = ALL_STAGES.map((s) => s.key)
const stageByKey = Object.fromEntries(ALL_STAGES.map((s) => [s.key, s]))

/** 根据难度返回本单实际经过的环节（有序），用于步骤条与推进逻辑 */
function getEffectiveStages(difficulty) {
  if (!difficulty) return [ALL_STAGES[0]]
  if (difficulty === 'simple') {
    return ALL_STAGES.filter((s) => !['project_manager', 'review'].includes(s.key))
  }
  if (difficulty === 'normal') {
    return ALL_STAGES.filter((s) => s.key !== 'review')
  }
  return [...ALL_STAGES]
}

/** 各阶段在 project 上展示的进度字段 */
const stageProgressMap = {
  reception: [
    { key: 'customerReceptionTime', label: '客户接待时间' },
    { key: 'customerDeadlineTime', label: '客户交稿时间' },
    { key: 'clientShortName', label: '客户简称' }
  ],
  project_manager: [
    { key: 'translatorCooperationType', label: '译员合作形式' },
    { key: 'translatorAssignee', label: '译员安排' },
    { key: 'translatorAssignmentTime', label: '译员安排时间' }
  ],
  project_specialist: [
    { key: 'translatorAssignee', label: '译员' },
    { key: 'translatorAssignmentTime', label: '译员安排时间' }
  ],
  project_assistant: [
    { key: 'translatorAssignee', label: '译员' },
    { key: 'translatorDeliveryProgress', label: '译员交稿进度' }
  ],
  translator: [
    { key: 'translatorAssignee', label: '译员' },
    { key: 'translatorDeliveryProgress', label: '译员交稿进度' }
  ],
  review: [
    { key: 'review1Progress', label: '审核进度' },
    { key: 'postReviewQcProgress', label: '审核后专检进度' }
  ],
  completed: [
    { key: 'sentToClientTime', label: '发客户时间' },
    { key: 'clientFeedback', label: '客户反馈' }
  ]
}

// ---------- 当前项目流程状态（未接后端时按项目 ID 存内存） ----------
const workflowStateByProject = reactive({})

function getWorkflowState(projectId) {
  if (projectId === undefined || projectId === null || projectId === '') return null
  const key = String(projectId)
  if (!workflowStateByProject[key]) {
    // 必须用 reactive() 包装，否则在 completeCurrentStage 等中修改 currentStageKey 等属性时
    // 不会触发视图更新（动态赋值的普通对象不是响应式的）
    workflowStateByProject[key] = reactive({
      difficulty: null,
      currentStageKey: 'reception',
      currentAssigneeUserId: null,
      currentAssigneeUserName: null,
      stageNotes: {},
      transitionLog: [
        {
          at: formatDateTime(new Date()),
          fromStage: '',
          toStage: 'reception',
          toTitle: '客户专员',
          direction: 'forward',
          description: '进入接稿（客户专员）',
          operator: '系统'
        }
      ]
    })
  }
  return workflowStateByProject[key]
}

const currentProjectId = ref('')
const projectList = ref([])
const handoverNote = ref('')
const activeTab = ref('my_tasks')
const fileList = ref([])

const rollbackDialogVisible = ref(false)
const rollbackSteps = ref(1)
const rollbackNote = ref('')

const nextAssigneeUserId = ref('')
const pendingDifficulty = ref(null)
const nextStageUsers = ref([])
const nextStageUsersLoading = ref(false)
const stageCardRef = ref(null)
/** 从「待我处理」点「进入」时保存的行对象，保证阶段卡片一定能显示（避免 id 匹配不到） */
const selectedProjectRow = ref(null)

const currentProject = computed(() => {
  if (selectedProjectRow.value) return selectedProjectRow.value
  const id = currentProjectId.value
  if (id === undefined || id === null || id === '') return undefined
  return projectList.value.find((p) => String(p.id) === String(id))
})

const workflowState = computed(() => getWorkflowState(currentProjectId.value) || {})

const effectiveSteps = computed(() => getEffectiveStages(workflowState.value.difficulty))

const currentStage = computed(() => stageByKey[workflowState.value.currentStageKey] ?? null)

const currentStepIndexInFlow = computed(() => {
  const key = workflowState.value.currentStageKey
  const idx = effectiveSteps.value.findIndex((s) => s.key === key)
  return idx >= 0 ? idx : 0
})

const isAtReception = computed(() => workflowState.value.currentStageKey === 'reception')

const isCurrentStageDone = computed(() => {
  const note = workflowState.value.stageNotes?.[workflowState.value.currentStageKey]
  return note !== undefined && note !== ''
})

const stageNoteForCurrentStage = computed(
  () => workflowState.value.stageNotes?.[workflowState.value.currentStageKey] ?? ''
)

const currentStageProgressFields = computed(
  () => stageProgressMap[workflowState.value.currentStageKey] || []
)

const transitionLog = computed(() => workflowState.value.transitionLog || [])

const canRollbackOne = computed(() => {
  const steps = effectiveSteps.value
  const idx = steps.findIndex((s) => s.key === workflowState.value.currentStageKey)
  return idx > 0
})

const canRollbackTwo = computed(() => {
  const steps = effectiveSteps.value
  const idx = steps.findIndex((s) => s.key === workflowState.value.currentStageKey)
  return idx >= 2
})

const currentUserName = computed(() => {
  try {
    return (localStorage.getItem('user_name') || '').trim() || '当前用户'
  } catch {
    return '当前用户'
  }
})

/** 当前用户是否为客户专员（用于展示「待设定难度」的接稿项目） */
const isCustomerSpecialist = computed(() => {
  const roles = getStoredRoles()
  return roles.includes('客户专员')
})

const nextStageAfterReception = computed(() => {
  if (workflowState.value.currentStageKey !== 'reception' || !pendingDifficulty.value) return null
  const steps = getEffectiveStages(pendingDifficulty.value)
  return steps[1] || null
})

const nextStageForAssignee = computed(() => {
  const state = getWorkflowState(currentProjectId.value)
  if (!state || state.currentStageKey === 'completed') return null
  const steps = getEffectiveStages(state.difficulty)
  const idx = steps.findIndex((s) => s.key === state.currentStageKey)
  if (idx < 0 || idx >= steps.length - 1) return null
  return steps[idx + 1] || null
})

const myTaskProjects = computed(() => {
  const name = currentUserName.value
  if (!name) return []
  return projectList.value.filter((p) => {
    const state = getWorkflowState(p.id)
    if (!state || state.currentStageKey === 'completed') return false
    // 已指定负责人且是自己 → 待我处理
    if (state.currentAssigneeUserName === name) return true
    // 客户专员：当前阶段为接稿且未设定难度的项目也视为「待我处理」（需设定难度）
    if (isCustomerSpecialist.value && state.currentStageKey === 'reception' && !state.difficulty) return true
    return false
  })
})

const nextStageToAssign = computed(() => nextStageAfterReception.value || nextStageForAssignee.value)

watch(nextStageToAssign, async (stage) => {
  nextAssigneeUserId.value = ''
  if (!stage || !stage.role) {
    nextStageUsers.value = []
    return
  }
  nextStageUsersLoading.value = true
  try {
    const list = await getUsersByRoleName(stage.role)
    nextStageUsers.value = list || []
  } catch (e) {
    console.error(e)
    nextStageUsers.value = []
  } finally {
    nextStageUsersLoading.value = false
  }
}, { immediate: true })

const projectProgress = computed(() => {
  const p = currentProject.value
  if (!p) return {}
  return {
    orderNo: p.orderNo,
    projectName: p.projectName,
    clientShortName: p.clientShortName,
    clientCode: p.clientCode,
    customerReceptionTime: p.customerReceptionTime,
    customerDeadlineTime: p.customerDeadlineTime,
    translatorCooperationType: p.translatorCooperationType,
    translatorAssignee: p.translatorAssignee,
    translatorAssignmentTime: p.translatorAssignmentTime,
    translatorDeliveryProgress: p.translatorDeliveryProgress,
    review1Progress: p.review1Progress,
    preReviewQcProgress: p.preReviewQcProgress,
    layoutProgress: p.layoutProgress,
    consolidationProgress: p.consolidationProgress,
    sentToClientTime: p.sentToClientTime,
    clientFeedback: p.clientFeedback,
    postReviewQcProgress: p.postReviewQcProgress,
    review2Progress: p.review2Progress
  }
})

function formatDateTime(d) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function difficultyLabel(d) {
  const map = { simple: '简单', normal: '普通', complex: '复杂' }
  return map[d] || d
}

function getStatusLabel(status) {
  const map = { pending: '待启动', in_progress: '进行中', completed: '已完成', paused: '已暂停' }
  return map[status] || status
}

function getStatusType(status) {
  const map = { pending: 'info', in_progress: 'warning', completed: 'success', paused: 'danger' }
  return map[status] || ''
}

function appendLog(state, entry) {
  state.transitionLog = state.transitionLog || []
  state.transitionLog.push(entry)
}

function confirmDifficulty() {
  const state = getWorkflowState(currentProjectId.value)
  if (!state || !pendingDifficulty.value || !nextAssigneeUserId.value) return
  state.difficulty = pendingDifficulty.value
  const steps = getEffectiveStages(state.difficulty)
  const nextIdx = 1
  if (nextIdx >= steps.length) return
  const next = steps[nextIdx]
  const selectedUser = nextStageUsers.value.find((u) => u.id === nextAssigneeUserId.value)
  const nextUserName = selectedUser ? (selectedUser.full_name || selectedUser.username || selectedUser.id) : ''
  appendLog(state, {
    at: formatDateTime(new Date()),
    fromStage: 'reception',
    toStage: next.key,
    toTitle: next.title,
    direction: 'forward',
    description: `确认难度为「${difficultyLabel(state.difficulty)}」，进入${next.title}，指定负责人：${nextUserName}`,
    operator: '客户专员',
    nextAssigneeUserId: nextAssigneeUserId.value,
    nextAssigneeUserName: nextUserName
  })
  state.currentStageKey = next.key
  state.currentAssigneeUserId = nextAssigneeUserId.value
  state.currentAssigneeUserName = nextUserName
  nextAssigneeUserId.value = ''
  pendingDifficulty.value = null
  ElMessage.success('难度已确认，已指定下一环节负责人，流程已推进')
}

function completeCurrentStage() {
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return
  const steps = getEffectiveStages(state.difficulty)
  const idx = steps.findIndex((s) => s.key === state.currentStageKey)
  if (idx < 0) return
  const nextIdx = idx + 1
  const next = nextIdx < steps.length ? steps[nextIdx] : null
  if (next && !nextAssigneeUserId.value) return
  const note = handoverNote.value?.trim() || '（无备注）'
  state.stageNotes = state.stageNotes || {}
  state.stageNotes[state.currentStageKey] = note
  handoverNote.value = ''
  const currentStageInfo = stageByKey[state.currentStageKey]
  if (nextIdx >= steps.length) {
    appendLog(state, {
      at: formatDateTime(new Date()),
      fromStage: state.currentStageKey,
      toStage: 'completed',
      toTitle: '完成',
      direction: 'forward',
      description: `从「${currentStageInfo?.title || state.currentStageKey}」进入「完成」`,
      note,
      operator: currentStageInfo?.role || '-'
    })
    state.currentStageKey = 'completed'
    state.currentAssigneeUserId = null
    state.currentAssigneeUserName = null
    nextAssigneeUserId.value = ''
    ElMessage.success('本阶段已完成')
    return
  }
  const selectedUser = nextStageUsers.value.find((u) => u.id === nextAssigneeUserId.value)
  const nextUserName = selectedUser ? (selectedUser.full_name || selectedUser.username || selectedUser.id) : ''
  appendLog(state, {
    at: formatDateTime(new Date()),
    fromStage: state.currentStageKey,
    toStage: next.key,
    toTitle: next.title,
    direction: 'forward',
    description: `从「${currentStageInfo?.title || state.currentStageKey}」进入「${next.title}」，指定负责人：${nextUserName}`,
    note,
    operator: currentStageInfo?.role || '-',
    nextAssigneeUserId: nextAssigneeUserId.value,
    nextAssigneeUserName: nextUserName
  })
  state.currentStageKey = next.key
  state.currentAssigneeUserId = nextAssigneeUserId.value
  state.currentAssigneeUserName = nextUserName
  nextAssigneeUserId.value = ''
  ElMessage.success('本阶段已完成，已指定下一环节负责人，流程已推进')
}

function openRollbackDialog(steps) {
  rollbackSteps.value = steps
  rollbackNote.value = ''
  rollbackDialogVisible.value = true
}

function confirmRollback() {
  const note = rollbackNote.value?.trim()
  if (!note) return
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return
  const steps = getEffectiveStages(state.difficulty)
  const idx = steps.findIndex((s) => s.key === state.currentStageKey)
  const backSteps = rollbackSteps.value
  const targetIdx = Math.max(0, idx - backSteps)
  const target = steps[targetIdx]
  const currentStageInfo = stageByKey[state.currentStageKey]
  appendLog(state, {
    at: formatDateTime(new Date()),
    fromStage: state.currentStageKey,
    toStage: target.key,
    toTitle: target.title,
    direction: 'rollback',
    description: `打回至「${target.title}」`,
    note,
    operator: currentStageInfo?.role || '-'
  })
  state.currentStageKey = target.key
  // 清除目标阶段的旧备注，使其可重新处理
  if (state.stageNotes) {
    delete state.stageNotes[target.key]
  }
  rollbackDialogVisible.value = false
  rollbackNote.value = ''
  handoverNote.value = ''
  ElMessage.success(`已打回至「${target.title}」`)
}

async function loadProjects() {
  try {
    if (isMockEnabled()) {
      const { getMockTranslationProjects } = await import('@/mock/data')
      projectList.value = getMockTranslationProjects()
    } else {
      const res = await getProjects({ page: 1, limit: 100 })
      projectList.value = Array.isArray(res) ? res : []
    }
    if (projectList.value.length && !currentProjectId.value) {
      currentProjectId.value = projectList.value[0].id
    }
  } catch (e) {
    console.error(e)
    projectList.value = []
  }
}

function onProjectChange() {
  selectedProjectRow.value = null
  handoverNote.value = ''
  nextAssigneeUserId.value = ''
  pendingDifficulty.value = null
}

function selectProject(projectIdOrRow) {
  const isRow = projectIdOrRow != null && typeof projectIdOrRow === 'object' && 'id' in projectIdOrRow
  if (isRow) {
    currentProjectId.value = projectIdOrRow.id
    selectedProjectRow.value = projectIdOrRow
  } else {
    currentProjectId.value = projectIdOrRow
    selectedProjectRow.value = null
  }
  handoverNote.value = ''
  nextAssigneeUserId.value = ''
  pendingDifficulty.value = null
  activeTab.value = 'overview'
  nextTick(() => {
    const el = stageCardRef.value?.$el ?? stageCardRef.value
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

function onMyTaskRowClick(row) {
  if (row && row.id) selectProject(row)
}

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

.workflow-steps {
  margin-bottom: 24px;
}

.stage-card {
  margin-bottom: 20px;
  border: 1px solid var(--el-border-color-lighter);
}

.stage-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.stage-name {
  font-weight: 600;
  font-size: 15px;
}

.assignee-tag {
  margin-left: 4px;
}

.difficulty-tag {
  margin-left: auto;
}

.section-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.stage-difficulty .handover-hint,
.stage-handover .handover-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px 0;
}

.difficulty-radio {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.stage-difficulty .action-hint {
  font-size: 13px;
  color: var(--el-color-warning);
  margin: 0 0 10px 0;
}

.stage-progress {
  margin-bottom: 20px;
}

.readonly-value {
  color: var(--el-text-color-regular);
}

.stage-handover-readonly .readonly-note {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 0 0 8px 0;
}

.stage-actions {
  margin-top: 12px;
}

.stage-actions-multi {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.readonly-note {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
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
