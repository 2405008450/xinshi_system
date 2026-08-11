import { computed, onUnmounted, reactive, ref, watch } from 'vue'

import {
  getMyTasksAPI,
  getProjectRoleCandidatesAPI,
  getSubOrderWorkflowStateAPI,
  getWorkflowConfigAPI,
  getWorkflowStateAPI,
  initSubOrderWorkflowAPI,
  initWorkflowAPI,
  rollbackSubOrderWorkflowAPI,
  rollbackWorkflowAPI,
  setSubOrderDifficultyAPI,
  setDifficultyAPI,
  transitionSubOrderWorkflowAPI,
  transitionWorkflowAPI,
  updateStageDataAPI,
  updateSubOrderStageDataAPI
} from '@/api/workflow'

const FALLBACK_STAGE_DEFINITIONS = [
  { key: 'reception', title: '客户专员', role: '客户专员', roleCode: 'customer_specialist' },
  { key: 'layout_assign', title: '预处理', role: '排版专员', roleCode: 'layout_specialist' },
  { key: 'project_manager', title: '项目经理', role: '项目经理', roleCode: 'project_manager' },
  { key: 'project_specialist', title: '项目专员', role: '项目专员', roleCode: 'project_specialist' },
  { key: 'project_assistant', title: '项目助理', role: '项目助理', roleCode: 'project_assistant' },
  { key: 'review', title: '译审', role: '译审', roleCode: 'reviewer' },
  { key: 'special_qc', title: '专检', role: '项目专员', roleCode: 'project_specialist' },
  { key: 'layout', title: '排版', role: '排版专员', roleCode: 'layout_specialist' },
  { key: 'completed', title: '完成', role: '-', roleCode: 'completed' }
]

const PROJECT_STATUS_OPTIONS = [
  { label: '进行中', value: 'in_progress' },
  { label: '已暂停', value: 'paused' },
  { label: '已终止', value: 'terminated' }
]

const STATUS_LABEL_MAP = {
  pending: '待启动',
  in_progress: '进行中',
  completed: '已完成',
  paused: '已暂停',
  terminated: '已终止'
}

const STATUS_TYPE_MAP = {
  pending: 'info',
  in_progress: 'warning',
  completed: 'success',
  paused: 'danger',
  terminated: 'info'
}

const stageProgressMap = {
  reception: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'customerReceptionTime', label: '客户来稿时间', type: 'date' },
      { key: 'customerDeadlineTime', label: '交稿客户时间', type: 'date' },
      { key: 'fileTypeSecondary', label: '文本类型' },
      { key: 'languagePair', label: '翻译方向' },
      { key: 'wordCount', label: '字数统计' }
    ],
    readonly: [
      { key: 'clientShortName', label: '客户简称' }
    ]
  },
  layout_assign: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'layoutAssignNote', label: '预处理说明' }
    ],
    readonly: [
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'clientShortName', label: '客户简称' }
    ]
  },
  project_manager: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'priority', label: '优先级', type: 'select', options: ['低', '中', '高', '紧急'] },
      { key: 'wordCount', label: '预估字数' }
    ],
    readonly: [
      { key: 'customerReceptionTime', label: '客户接待时间' },
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'clientShortName', label: '客户简称' }
    ]
  },
  project_specialist: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'languagePair', label: '语言方向' },
      { key: 'fileTypeSecondary', label: '文本类型' }
    ],
    readonly: [
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'priority', label: '优先级' },
      { key: 'wordCount', label: '预估字数' }
    ]
  },
  project_assistant: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'translatorAssignee', label: '译员安排' },
      { key: 'translatorAssignmentTime', label: '译员安排时间', type: 'date' },
      { key: 'estimatedTime', label: '译员预计处理耗时' },
      { key: 'actualTime', label: '译员实际处理耗时' },
      { key: 'translatorDeliveryProgress', label: '译员交稿进度', type: 'select', options: ['未开始', '进行中', '已完成', '待审核', '已审核'] }
    ],
    readonly: [
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'languagePair', label: '翻译方向' },
      { key: 'priority', label: '优先级' }
    ]
  },
  review: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'review1Progress', label: '审核进度', type: 'select', options: ['未开始', '进行中', '已完成'] },
      { key: 'postReviewQcProgress', label: '审核后专检进度', type: 'select', options: ['未开始', '进行中', '已完成'] }
    ],
    readonly: [
      { key: 'translatorAssignee', label: '译员' },
      { key: 'translatorDeliveryProgress', label: '译员交稿进度' }
    ]
  },
  special_qc: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'specialQcResult', label: '专检结果', type: 'select', options: ['通过', '需修改', '驳回'] },
      { key: 'specialQcNote', label: '专检说明' }
    ],
    readonly: [
      { key: 'review1Progress', label: '审核进度' },
      { key: 'postReviewQcProgress', label: '审核后专检进度' },
      { key: 'translatorAssignee', label: '译员' }
    ]
  },
  layout: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'layoutProgress', label: '排版进度', type: 'select', options: ['未开始', '进行中', '已完成'] },
      { key: 'layoutNote', label: '排版备注' }
    ],
    readonly: [
      { key: 'specialQcResult', label: '专检结果' },
      { key: 'specialQcNote', label: '专检说明' }
    ]
  },
  completed: {
    editable: [],
    readonly: [
      { key: 'specialQcResult', label: '专检结果' },
      { key: 'layoutProgress', label: '排版进度' },
      { key: 'review1Progress', label: '审核进度' },
      { key: 'translatorAssignee', label: '译员' }
    ]
  }
}

function normalizeStageDefinitions(stages) {
  const fallbackByKey = Object.fromEntries(FALLBACK_STAGE_DEFINITIONS.map((stage) => [stage.key, stage]))
  const source = Array.isArray(stages) && stages.length ? stages : FALLBACK_STAGE_DEFINITIONS
  return source.map((stage) => {
    const fallback = fallbackByKey[stage.key] || {}
    return {
      ...fallback,
      ...stage,
      roleCode: stage.roleCode || stage.role_code || fallback.roleCode || ''
    }
  })
}

function formatLogTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').substring(0, 19)
}

function buildStoreKey(entityType, entityId) {
  if (!entityId) return ''
  return `${entityType}:${entityId}`
}

export function buildPreviewEffectiveStages(difficulty, fileEditable = true, stageDefinitions = FALLBACK_STAGE_DEFINITIONS) {
  const stages = normalizeStageDefinitions(stageDefinitions)
  if (!difficulty) return [stages[0]]

  const shouldKeepLayoutAssign = fileEditable === false || fileEditable === 'no'
  let steps = [...stages]
  if (!shouldKeepLayoutAssign) {
    steps = steps.filter((stage) => stage.key !== 'layout_assign')
  }

  if (difficulty === 'simple') {
    return steps.filter((stage) => !['project_manager', 'project_specialist', 'review'].includes(stage.key))
  }

  if (difficulty === 'normal') {
    return steps.filter((stage) => stage.key !== 'review')
  }

  return steps
}

function normalizeWorkflowPayload(payload, stageDefinitions) {
  const difficulty = payload?.difficulty ?? null
  const fileEditable = payload?.fileEditable ?? payload?.file_editable ?? null
  const effectiveStages = normalizeStageDefinitions(
    payload?.effectiveStages ||
    payload?.effective_stages ||
    buildPreviewEffectiveStages(difficulty, fileEditable, stageDefinitions)
  )

  return {
    id: payload?.id ? String(payload.id) : '',
    translationProjectId: payload?.translationProjectId || payload?.translation_project_id ? String(payload.translationProjectId || payload.translation_project_id) : '',
    subOrderId: payload?.subOrderId || payload?.sub_order_id ? String(payload.subOrderId || payload.sub_order_id) : '',
    subOrderNo: payload?.subOrderNo || payload?.sub_order_no || '',
    difficulty,
    fileEditable,
    currentStageKey: payload?.currentStageKey || payload?.current_stage_key || '',
    currentStageRoleCode: payload?.currentStageRoleCode || payload?.current_stage_role_code || '',
    currentStageRoleName: payload?.currentStageRoleName || payload?.current_stage_role_name || '',
    currentAssigneeUserId: payload?.currentAssigneeUserId || payload?.current_assignee_id ? String(payload.currentAssigneeUserId || payload.current_assignee_id) : '',
    currentAssigneeUserName: payload?.currentAssigneeUserName || payload?.current_assignee_name || '',
    groupAssignRole: payload?.groupAssignRole || payload?.group_assign_role || '',
    projectStatus: payload?.projectStatus || payload?.project_status || '',
    stageNotes: payload?.stageNotes || payload?.stage_notes || {},
    stageData: payload?.stageData || payload?.stage_data || {},
    effectiveStages,
    roleAssignments: payload?.roleAssignments || payload?.role_assignments || [],
    transitionLog: (payload?.transitionLog || payload?.logs || []).map((log) => ({
      at: formatLogTime(log?.at || log?.created_at),
      fromStage: log?.fromStage || log?.from_stage || '',
      toStage: log?.toStage || log?.to_stage || '',
      direction: log?.direction || '',
      description: log?.description || '',
      operator: log?.operator || log?.operator_name || '',
      note: log?.note || '',
      nextAssigneeUserId: log?.nextAssigneeUserId || log?.next_assignee_id ? String(log.nextAssigneeUserId || log.next_assignee_id) : '',
      nextAssigneeUserName: log?.nextAssigneeUserName || log?.next_assignee_name || ''
    })),
    createdAt: formatLogTime(payload?.createdAt || payload?.created_at),
    updatedAt: formatLogTime(payload?.updatedAt || payload?.updated_at)
  }
}

export function difficultyLabel(difficulty) {
  const labels = {
    simple: '简单',
    normal: '普通',
    complex: '复杂'
  }
  return labels[difficulty] || difficulty || '未设定'
}

export function getStatusLabel(status) {
  return STATUS_LABEL_MAP[status] || status || '待启动'
}

export function getStatusType(status) {
  return STATUS_TYPE_MAP[status] || 'info'
}

export function useWorkflow() {
  const workflowConfigLoaded = ref(false)
  const stageDefinitions = ref([...FALLBACK_STAGE_DEFINITIONS])
  const workflowStateByEntity = reactive({})
  const myTaskList = ref([])

  const stageByKey = computed(() => Object.fromEntries(stageDefinitions.value.map((stage) => [stage.key, stage])))

  async function loadWorkflowConfig(force = false) {
    if (workflowConfigLoaded.value && !force) return stageDefinitions.value

    try {
      const response = await getWorkflowConfigAPI()
      const stages = response?.allStages || response?.all_stages
      if (Array.isArray(stages) && stages.length) {
        stageDefinitions.value = normalizeStageDefinitions(stages)
      } else {
        stageDefinitions.value = [...FALLBACK_STAGE_DEFINITIONS]
      }
    } catch {
      stageDefinitions.value = [...FALLBACK_STAGE_DEFINITIONS]
    } finally {
      workflowConfigLoaded.value = true
    }

    return stageDefinitions.value
  }

  function getWorkflowState(entityType, entityId) {
    const key = buildStoreKey(entityType, entityId)
    if (!key) return null
    return workflowStateByEntity[key] || null
  }

  function setWorkflowState(entityType, entityId, payload) {
    const key = buildStoreKey(entityType, entityId)
    if (!key) return null

    if (!workflowStateByEntity[key]) {
      workflowStateByEntity[key] = reactive({})
    }

    Object.assign(
      workflowStateByEntity[key],
      normalizeWorkflowPayload(payload, stageDefinitions.value)
    )

    return workflowStateByEntity[key]
  }

  async function loadMyTasks() {
    try {
      const tasks = await getMyTasksAPI()
      myTaskList.value = Array.isArray(tasks) ? tasks : []
    } catch {
      myTaskList.value = []
    }

    return myTaskList.value
  }

  async function ensureWorkflowState(entityType, entityId) {
    if (!entityId) return null
    await loadWorkflowConfig()

    if (entityType === 'suborder') {
      let state
      try {
        state = await getSubOrderWorkflowStateAPI(entityId)
      } catch (error) {
        if (error?.response?.status === 404 || error?.status === 404) {
          state = await initSubOrderWorkflowAPI(entityId)
        } else {
          throw error
        }
      }
      return setWorkflowState(entityType, entityId, state)
    }

    let state
    try {
      state = await getWorkflowStateAPI(entityId)
    } catch (error) {
      if (error?.response?.status === 404 || error?.status === 404) {
        state = await initWorkflowAPI(entityId)
      } else {
        throw error
      }
    }
    return setWorkflowState(entityType, entityId, state)
  }

  async function submitDifficulty(entityType, entityId, payload) {
    const response = entityType === 'suborder'
      ? await setSubOrderDifficultyAPI(entityId, payload)
      : await setDifficultyAPI(entityId, payload)
    setWorkflowState(entityType, entityId, response)
    return response
  }

  async function saveStageData(entityType, entityId, payload) {
    const response = entityType === 'suborder'
      ? await updateSubOrderStageDataAPI(entityId, payload)
      : await updateStageDataAPI(entityId, payload)
    setWorkflowState(entityType, entityId, response)
    return response
  }

  async function transitionStage(entityType, entityId, payload) {
    const response = entityType === 'suborder'
      ? await transitionSubOrderWorkflowAPI(entityId, payload)
      : await transitionWorkflowAPI(entityId, payload)
    setWorkflowState(entityType, entityId, response)
    return response
  }

  async function rollbackStage(entityType, entityId, payload) {
    const response = entityType === 'suborder'
      ? await rollbackSubOrderWorkflowAPI(entityId, payload)
      : await rollbackWorkflowAPI(entityId, payload)
    setWorkflowState(entityType, entityId, response)
    return response
  }

  return {
    PROJECT_STATUS_OPTIONS,
    difficultyLabel,
    getStatusLabel,
    getStatusType,
    loadMyTasks,
    loadWorkflowConfig,
    myTaskList,
    stageByKey,
    stageDefinitions,
    stageProgressMap,
    setWorkflowState,
    workflowStateByEntity,
    getWorkflowState,
    ensureWorkflowState,
    submitDifficulty,
    saveStageData,
    transitionStage,
    rollbackStage
  }
}

export function useNextStageUsers(nextStageRef) {
  const nextStageUsers = ref([])
  const nextStageUsersLoading = ref(false)
  let loadVersion = 0

  const stop = watch(
    nextStageRef,
    async (stage) => {
      const version = ++loadVersion
      const roleCode = stage?.roleCode || stage?.role_code
      if (!stage || !roleCode || stage.role === '-' || roleCode === 'completed') {
        nextStageUsers.value = []
        nextStageUsersLoading.value = false
        return
      }

      nextStageUsersLoading.value = true

      try {
        const list = await getProjectRoleCandidatesAPI(roleCode)
        if (version !== loadVersion) return

        if (version !== loadVersion) return
        nextStageUsers.value = list
      } catch {
        if (version !== loadVersion) return
        nextStageUsers.value = []
      } finally {
        if (version === loadVersion) {
          nextStageUsersLoading.value = false
        }
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    stop()
    loadVersion += 1
  })

  return {
    nextStageUsers,
    nextStageUsersLoading
  }
}
