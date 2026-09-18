<template>
  <DraggableFormDialog
    :model-value="modelValue"
    title="项目安排"
    width="min(1280px, calc(100vw - 32px))"
    top="5vh"
    class="annotation-arrangement-dialog"
    append-to-body
    destroy-on-close
    :before-close="beforeClose"
    @update:model-value="emit('update:modelValue', $event)"
    @open="initialize"
    @closed="resetState"
  >
    <div class="arrangement-toolbar">
      <el-select
        v-model="projectToAdd"
        filterable
        remote
        clearable
        reserve-keyword
        placeholder="搜索订单号、项目名称或客户名称，添加其他标注项目"
        :remote-method="searchProjects"
        :loading="projectSearchLoading"
        class="project-search"
        @keyup.enter="searchProjects(projectKeyword)"
        @change="addSelectedProject"
        @visible-change="(visible) => visible && !projectKeyword.trim() && searchProjects('')"
      >
        <el-option
          v-for="item in availableProjectOptions"
          :key="item.id"
          :label="projectOptionLabel(item)"
          :value="item.id"
        />
      </el-select>
      <el-select v-model="projectSortOrder" class="project-sort-select" aria-label="项目名称排序">
        <el-option label="项目名称：默认顺序" value="" />
        <el-option label="项目名称：升序" value="ascending" />
        <el-option label="项目名称：降序" value="descending" />
      </el-select>
      <el-popover v-if="canWrite" trigger="click" placement="bottom-end" :width="440">
        <template #reference><el-button>任务类型管理</el-button></template>
        <div class="task-type-manager">
          <div class="task-type-create">
            <el-input v-model="newTaskTypeName" maxlength="50" placeholder="新增任务类型" @keyup.enter="createTaskType" />
            <el-button type="primary" :loading="taskTypeSaving" @click="createTaskType">新增</el-button>
          </div>
          <div class="task-type-list">
            <div v-for="item in taskTypes" :key="item.id" class="task-type-row">
              <el-input v-if="editingTaskTypeId === item.id" v-model="editingTaskTypeName" maxlength="50" size="small" @keyup.enter="saveTaskTypeName(item)" />
              <span v-else :class="{ 'is-inactive': !item.isActive }">{{ item.name }}</span>
              <div class="task-type-actions">
                <el-button v-if="editingTaskTypeId === item.id" type="primary" link size="small" @click="saveTaskTypeName(item)">保存</el-button>
                <el-button v-else type="primary" link size="small" @click="startEditTaskType(item)">改名</el-button>
                <el-button :type="item.isActive ? 'warning' : 'success'" link size="small" @click="toggleTaskType(item)">{{ item.isActive ? '停用' : '恢复' }}</el-button>
              </div>
            </div>
            <el-empty v-if="!taskTypes.length" description="暂无任务类型" :image-size="52" />
          </div>
        </div>
      </el-popover>
      <span class="toolbar-summary">已选择 {{ formModel.projects.length }} 个项目</span>
    </div>

    <AppForm ref="formRef" :model="formModel" label-position="top" class="arrangement-form">
      <div class="project-arrangement-list">
        <article v-for="(project, projectIndex) in sortedProjects" :key="project.id" class="project-arrangement-row">
          <aside class="project-summary-panel">
            <div class="project-sequence">项目 {{ projectIndex + 1 }}</div>
            <div class="project-identity">
              <strong :title="textValue(project.orderNo)">{{ textValue(project.orderNo) }}</strong>
              <span :title="textValue(project.projectName)">{{ textValue(project.projectName) }}</span>
            </div>
            <dl class="project-summary-list">
              <div>
                <dt>客户名称</dt>
                <dd :title="textValue(project.clientName)">{{ textValue(project.clientName) }}</dd>
              </div>
              <div>
                <dt>具体任务</dt>
                <dd>
                  <el-tooltip :content="textValue(project.taskDescription)" placement="top" :disabled="!project.taskDescription">
                    <span class="project-task-summary">{{ textValue(project.taskDescription) }}</span>
                  </el-tooltip>
                </dd>
              </div>
              <div>
                <dt>项目进度</dt>
                <dd>
                  <el-button class="project-status-button" type="primary" link @click="toggleProgress(project)">
                    <el-tag :type="statusType(project.projectStatus)" size="small">{{ statusLabel(project.projectStatus) }}</el-tag>
                  </el-button>
                </dd>
              </div>
              <div>
                <dt>任务数量</dt>
                <dd>{{ project.tasks.length }} 条安排</dd>
              </div>
            </dl>
            <el-button
              v-if="formModel.projects.length > 1"
              class="remove-project-button"
              type="danger"
              link
              size="small"
              @click="removeProject(project)"
            >
              移出本次窗口
            </el-button>
          </aside>

          <section class="project-arrangement-panel">
            <header class="project-arrangement-header">
              <div>
                <strong>任务与安排</strong>
                <span>为该项目维护一条或多条执行任务</span>
              </div>
              <div class="project-arrangement-actions">
                <el-button type="primary" link size="small" @click="toggleProgress(project)">
                  {{ progressOpenIds.has(project.id) ? '收起具体进度' : '查看具体进度' }}
                </el-button>
                <el-button v-if="canWrite" type="primary" plain size="small" @click="addTask(project)">新增任务</el-button>
              </div>
            </header>

            <section v-if="progressOpenIds.has(project.id)" class="inline-progress-panel">
            <div class="inline-progress-header">
              <strong>具体进度</strong>
              <span>只允许补充或编辑具体进度，不在此切换项目状态</span>
              <el-button type="primary" link :loading="progressLoadingIds.has(project.id)" @click="loadProgress(project, true)">刷新</el-button>
            </div>
            <div v-loading="progressLoadingIds.has(project.id)" class="progress-groups">
              <div v-for="group in progressGroups(project)" :key="group.key" class="progress-group">
                <div class="progress-group__title">
                  <el-tag :type="statusType(group.status)" size="small">{{ statusLabel(group.status) }}</el-tag>
                  <span>{{ formatDateTime(group.effectiveOn) }}</span>
                  <el-tag v-if="group.isCurrent" type="success" size="small" effect="plain">当前状态</el-tag>
                  <el-button v-if="canWrite" type="primary" link size="small" @click="startNewProgress(project, group)">补充进度</el-button>
                </div>
                <div v-if="group.children.length" class="progress-items">
                  <div v-for="record in group.children" :key="record.key" class="progress-item">
                    <div><span class="progress-time">{{ formatDateTime(record.effectiveOn) }}</span>{{ record.changeNote }}</div>
                    <el-button v-if="canWrite && record.kind === 'progress'" type="primary" link size="small" @click="startEditProgress(project, record)">编辑</el-button>
                  </div>
                </div>
                <span v-else class="muted">暂无具体进度</span>
              </div>
              <el-empty v-if="!progressLoadingIds.has(project.id) && !progressGroups(project).length" description="暂无项目进度" :image-size="52" />
            </div>
            <AppForm v-if="canWrite && progressEditors[project.id]" :model="progressEditors[project.id]" label-width="76px" size="small" class="progress-editor">
              <el-row :gutter="12">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="所属状态"><ReadonlyField :model-value="statusLabel(progressEditors[project.id].projectStatus)" source="auto" /></el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="节点时间"><el-date-picker v-model="progressEditors[project.id].effectiveOn" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" /></el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="具体进度">
                <el-input v-model="progressEditors[project.id].changeNote" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="10000" show-word-limit />
              </el-form-item>
              <div class="progress-editor__actions">
                <el-button size="small" @click="cancelProgressEdit(project.id)">取消</el-button>
                <el-button type="primary" size="small" :loading="progressSavingIds.has(project.id)" @click="saveProgress(project)">保存具体进度</el-button>
              </div>
            </AppForm>
            </section>

            <el-table :data="project.tasks" border size="small" class="arrangement-task-table">
            <el-table-column prop="executionDate" label="执行日期" width="170" sortable :sort-method="compareExecutionDate">
              <template #default="{ row: task }">
                <el-form-item :prop="taskFormProp(project, task, 'executionDate')" :rules="requiredRule('请选择执行日期', 'change')">
                  <el-date-picker v-model="task.executionDate" type="date" value-format="YYYY-MM-DD" style="width:100%" :disabled="!canWrite" @change="markDirty(task)" />
                </el-form-item>
              </template>
            </el-table-column>
            <el-table-column prop="taskTypeId" label="任务类型" min-width="190" sortable :sort-method="compareTaskType">
              <template #default="{ row: task }">
                <el-form-item :prop="taskFormProp(project, task, 'taskTypeId')" :rules="requiredRule('请选择任务类型', 'change')">
                  <el-select
                    v-model="task.taskTypeId"
                    filterable
                    allow-create
                    default-first-option
                    style="width:100%"
                    :disabled="!canWrite"
                    @change="(value) => selectTaskType(task, value)"
                  >
                    <el-option v-for="item in taskTypeOptions(task)" :key="item.id" :label="item.isActive ? item.name : `${item.name}（已停用）`" :value="item.id" :disabled="!item.isActive && item.id !== task.originalTaskTypeId" />
                  </el-select>
                </el-form-item>
              </template>
            </el-table-column>
            <el-table-column prop="assigneeId" label="执行人" min-width="190" sortable :sort-method="compareAssignee">
              <template #default="{ row: task }">
                <el-form-item :prop="taskFormProp(project, task, 'assigneeId')" :rules="requiredRule('请选择执行人', 'change')">
                  <el-select v-model="task.assigneeId" filterable style="width:100%" :disabled="!canWrite" @change="markDirty(task)">
                    <el-option-group v-for="group in assigneeGroups" :key="group.key" :label="group.label">
                      <el-option v-for="person in group.options" :key="person.id" :label="person.department ? `${person.displayName}（${person.department}）` : person.displayName" :value="person.id" />
                    </el-option-group>
                  </el-select>
                </el-form-item>
              </template>
            </el-table-column>
            <el-table-column label="任务内容" min-width="360">
              <template #default="{ row: task }">
                <el-form-item :prop="taskFormProp(project, task, 'taskContent')" :rules="requiredRule('请填写任务内容', 'blur')">
                  <el-input v-model="task.taskContent" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" maxlength="10000" show-word-limit :disabled="!canWrite" @input="markDirty(task)" />
                </el-form-item>
              </template>
            </el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="76" fixed="right" align="center">
              <template #default="{ row: task }"><el-button type="danger" link size="small" @click="removeTask(project, task)">删除</el-button></template>
            </el-table-column>
            </el-table>
            <el-empty v-if="!project.tasks.length" description="暂无项目安排，点击“新增任务”开始安排" :image-size="56" />
          </section>
        </article>
        <el-empty v-if="!formModel.projects.length" description="暂无已选项目" :image-size="72" />
      </div>
    </AppForm>

    <template #footer>
      <el-button @click="requestClose">取消</el-button>
      <el-button v-if="canWrite" type="primary" :loading="saving" @click="saveAll">保存全部</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as annotationApi from '@/api/annotationProjects'
import * as annotationOpsApi from '@/api/annotationOps'
import { groupAnnotationProgressRows } from '@/utils/annotationProgress'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialProject: { type: Object, default: null },
  defaultExecutionDate: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const formRef = ref(null)
const formModel = reactive({ projects: [] })
const taskTypes = ref([])
const assignees = ref([])
const deletedItems = ref([])
const saving = ref(false)
const initialized = ref(false)
const projectToAdd = ref('')
const projectSortOrder = ref('')
const projectOptions = ref([])
const projectKeyword = ref('')
const projectSearchLoading = ref(false)
const newTaskTypeName = ref('')
const editingTaskTypeId = ref('')
const editingTaskTypeName = ref('')
const taskTypeSaving = ref(false)
const progressOpenIds = ref(new Set())
const progressLoadingIds = ref(new Set())
const progressSavingIds = ref(new Set())
const progressRows = reactive({})
const progressEditors = reactive({})
let searchTimer = null
let searchController = null
let searchRequestId = 0
let newTaskSequence = 0

const statusMap = Object.fromEntries([
  ['initial_consultation','初步咨询'],['consultation_no_result','初步咨询后无结果'],['resource_sourcing','资源开拓'],['resource_sourcing_cancelled','取消资源开拓'],['trial_preparation','试标准备'],['trial_in_progress','试标中'],['trial_submitted','试标已提交'],['trial_passed','试标通过'],['trial_failed','试标未通过'],['trial_partially_passed','部分试标通过'],['project_in_progress','项目进行中'],['sent_to_client','已发客户'],['client_feedback','客户反馈'],['cancelled','已取消'],['partially_cancelled','已部分取消'],['paused','暂停'],['actively_abandoned','主动放弃'],['ended','已结束'],
])
const statusLabel = (value) => statusMap[value] || value || '-'
const statusType = (value) => ({ initial_consultation:'info',consultation_no_result:'info',resource_sourcing:'primary',resource_sourcing_cancelled:'danger',trial_preparation:'warning',trial_in_progress:'warning',trial_submitted:'primary',trial_passed:'success',trial_failed:'danger',trial_partially_passed:'warning',project_in_progress:'primary',sent_to_client:'success',client_feedback:'warning',cancelled:'danger',partially_cancelled:'warning',paused:'warning',actively_abandoned:'danger',ended:'success' }[value] || 'info')
const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
const requiredRule = (message, trigger) => [{ required: true, message, trigger }]

const tomorrowString = (now = new Date()) => {
  const hongKongNow = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }))
  hongKongNow.setDate(hongKongNow.getDate() + 1)
  return `${hongKongNow.getFullYear()}-${String(hongKongNow.getMonth() + 1).padStart(2, '0')}-${String(hongKongNow.getDate()).padStart(2, '0')}`
}
const localDateTimeValue = (value = new Date()) => {
  const date = new Date(value)
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
const hasDirtyChanges = computed(() => deletedItems.value.length > 0 || formModel.projects.some(project => project.tasks.some(task => task._dirty || !task.id)))
const availableProjectOptions = computed(() => projectOptions.value.filter(option => !formModel.projects.some(project => project.id === option.id)))
const compareText = (left, right) => String(left || '').localeCompare(String(right || ''), 'zh-CN', { numeric:true, sensitivity:'base' })
const sortedProjects = computed(() => {
  if (!projectSortOrder.value) return formModel.projects
  const direction = projectSortOrder.value === 'descending' ? -1 : 1
  return [...formModel.projects].sort((left, right) => direction * compareText(left.projectName, right.projectName))
})
const assigneeGroups = computed(() => [
  { key:'project_manager', label:'项目经理', options:assignees.value.filter(item => item.priorityGroup === 'project_manager') },
  { key:'hr', label:'HR', options:assignees.value.filter(item => item.priorityGroup === 'hr') },
  { key:'other', label:'其他员工', options:assignees.value.filter(item => item.priorityGroup === 'other') },
].filter(group => group.options.length))

const normalizeTask = (task) => ({
  ...task,
  _key: task.id || `new-${++newTaskSequence}`,
  expectedUpdatedAt: task.updatedAt || null,
  originalTaskTypeId: task.taskTypeId || '',
  _dirty: false,
})
const normalizeProject = (project) => ({ ...project, tasks:(project.tasks || []).map(normalizeTask) })
const projectOptionLabel = (item) => `${item.orderNo || '-'} · ${item.projectName || '未命名项目'}${item.clientShortName ? ` · ${item.clientShortName}` : ''}`
const markDirty = (task) => { task._dirty = true }
const taskTypeOptions = (task) => taskTypes.value.filter(item => item.isActive || item.id === task.originalTaskTypeId)
const taskTypeName = (task) => taskTypes.value.find(item => item.id === task.taskTypeId)?.name || ''
const assigneeName = (task) => assignees.value.find(item => item.id === task.assigneeId)?.displayName || ''
const compareExecutionDate = (left, right) => compareText(left.executionDate, right.executionDate)
const compareTaskType = (left, right) => compareText(taskTypeName(left), taskTypeName(right))
const compareAssignee = (left, right) => compareText(assigneeName(left), assigneeName(right))
const taskFormProp = (project, task, field) => {
  const projectIndex = formModel.projects.indexOf(project)
  const taskIndex = project.tasks.indexOf(task)
  return `projects.${projectIndex}.tasks.${taskIndex}.${field}`
}

function setLoadingId(target, id, active) {
  const next = new Set(target.value)
  if (active) next.add(id); else next.delete(id)
  target.value = next
}

async function loadContext(projectIds) {
  if (!projectIds.length) return
  const context = await annotationOpsApi.getProjectArrangementContext(projectIds)
  taskTypes.value = context.taskTypes || []
  assignees.value = context.assignees || []
  for (const project of context.projects || []) {
    if (!formModel.projects.some(item => item.id === project.id)) formModel.projects.push(normalizeProject(project))
  }
}

async function initialize() {
  if (initialized.value || !props.initialProject?.id) return
  initialized.value = true
  try {
    await loadContext([props.initialProject.id])
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '加载项目安排失败'))
  }
}

function resetState() {
  formModel.projects.splice(0)
  taskTypes.value = []
  assignees.value = []
  deletedItems.value = []
  projectOptions.value = []
  projectToAdd.value = ''
  projectSortOrder.value = ''
  initialized.value = false
  progressOpenIds.value = new Set()
  for (const key of Object.keys(progressRows)) delete progressRows[key]
  for (const key of Object.keys(progressEditors)) delete progressEditors[key]
}

async function searchProjects(keyword = '') {
  clearTimeout(searchTimer)
  projectKeyword.value = String(keyword || '')
  searchTimer = setTimeout(async () => {
    searchController?.abort()
    searchController = new AbortController()
    const current = ++searchRequestId
    projectSearchLoading.value = true
    try {
      const page = await annotationApi.getAnnotationProjectPage({ skip:0, limit:20, keyword:projectKeyword.value.trim() || undefined }, { signal:searchController.signal })
      if (current === searchRequestId) projectOptions.value = Array.isArray(page?.items) ? page.items : []
    } catch (error) {
      if (current === searchRequestId && error?.code !== 'ERR_CANCELED') ElMessage.error(getLocalizedErrorMessage(error, '搜索标注项目失败'))
    } finally {
      if (current === searchRequestId) projectSearchLoading.value = false
    }
  }, projectKeyword.value.trim() ? 400 : 0)
}

async function addSelectedProject(projectId) {
  if (!projectId) return
  projectToAdd.value = ''
  if (formModel.projects.some(project => project.id === projectId)) return
  try { await loadContext([projectId]) } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '添加项目失败')) }
}

async function removeProject(project) {
  if (project.tasks.some(task => task._dirty || !task.id)) {
    try { await ElMessageBox.confirm('该项目存在未保存修改，移出后将丢失这些修改，是否继续？', '移出项目', { type:'warning' }) } catch { return }
  }
  formModel.projects.splice(formModel.projects.findIndex(item => item.id === project.id), 1)
  deletedItems.value = deletedItems.value.filter(item => item.projectId !== project.id)
}

function addTask(project) {
  const executionDate = /^\d{4}-\d{2}-\d{2}$/.test(props.defaultExecutionDate)
    ? props.defaultExecutionDate
    : tomorrowString()
  project.tasks.push(normalizeTask({ projectId:project.id, executionDate, taskTypeId:'', assigneeId:'', taskContent:'' }))
}
function removeTask(project, task) {
  if (task.id) deletedItems.value.push({ id:task.id, expectedUpdatedAt:task.expectedUpdatedAt, projectId:project.id })
  project.tasks.splice(project.tasks.indexOf(task), 1)
}

async function selectTaskType(task, value) {
  if (taskTypes.value.some(item => item.id === value)) { markDirty(task); return }
  const name = String(value || '').trim()
  if (!name) { task.taskTypeId = ''; return }
  taskTypeSaving.value = true
  try {
    const created = await annotationOpsApi.createArrangementTaskType({ name })
    taskTypes.value.push(created)
    task.taskTypeId = created.id
    markDirty(task)
    ElMessage.success('任务类型已新增')
  } catch (error) {
    task.taskTypeId = ''
    ElMessage.error(getLocalizedErrorMessage(error, '新增任务类型失败'))
  } finally { taskTypeSaving.value = false }
}

async function createTaskType() {
  const name = newTaskTypeName.value.trim()
  if (!name) return ElMessage.warning('请输入任务类型')
  taskTypeSaving.value = true
  try {
    const created = await annotationOpsApi.createArrangementTaskType({ name })
    taskTypes.value.push(created)
    newTaskTypeName.value = ''
    ElMessage.success('任务类型已新增')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '新增任务类型失败')) }
  finally { taskTypeSaving.value = false }
}
function startEditTaskType(item) { editingTaskTypeId.value = item.id; editingTaskTypeName.value = item.name }
async function saveTaskTypeName(item) {
  const name = editingTaskTypeName.value.trim()
  if (!name) return ElMessage.warning('请输入任务类型')
  taskTypeSaving.value = true
  try {
    const updated = await annotationOpsApi.updateArrangementTaskType(item.id, { name, expectedUpdatedAt:item.updatedAt })
    Object.assign(item, updated)
    editingTaskTypeId.value = ''
    ElMessage.success('任务类型已更新')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '更新任务类型失败')) }
  finally { taskTypeSaving.value = false }
}
async function toggleTaskType(item) {
  try {
    const updated = await annotationOpsApi.setArrangementTaskTypeState(item.id, { isActive:!item.isActive, expectedUpdatedAt:item.updatedAt })
    Object.assign(item, updated)
    ElMessage.success(updated.isActive ? '任务类型已恢复' : '任务类型已停用')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '更新任务类型状态失败')) }
}

async function saveAll() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await annotationOpsApi.saveProjectArrangements({
      items:formModel.projects.flatMap(project => project.tasks.map(task => ({
        id:task.id || undefined, projectId:project.id, executionDate:task.executionDate,
        taskTypeId:task.taskTypeId, assigneeId:task.assigneeId,
        taskContent:task.taskContent.trim(), expectedUpdatedAt:task.expectedUpdatedAt,
      }))),
      deletedItems:deletedItems.value.map(item => ({ id:item.id, expectedUpdatedAt:item.expectedUpdatedAt })),
    })
    const ids = formModel.projects.map(project => project.id)
    formModel.projects.splice(0)
    deletedItems.value = []
    await loadContext(ids)
    ElMessage.success('项目安排已保存')
    emit('saved')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '保存项目安排失败')) }
  finally { saving.value = false }
}

async function toggleProgress(project) {
  const next = new Set(progressOpenIds.value)
  if (next.has(project.id)) next.delete(project.id); else next.add(project.id)
  progressOpenIds.value = next
  if (next.has(project.id) && !progressRows[project.id]) await loadProgress(project)
}
async function loadProgress(project, force = false) {
  if (!force && progressRows[project.id]) return
  setLoadingId(progressLoadingIds, project.id, true)
  try { progressRows[project.id] = await annotationOpsApi.getStatusHistory(project.id) }
  catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '加载具体进度失败')) }
  finally { setLoadingId(progressLoadingIds, project.id, false) }
}
const progressGroups = (project) => groupAnnotationProgressRows(progressRows[project.id] || [], project.projectStatus)
function startNewProgress(project, group) {
  progressEditors[project.id] = { historyId:'', projectStatus:group.status, effectiveOn:localDateTimeValue(), changeNote:'', expectedUpdatedAt:null }
}
function startEditProgress(project, record) {
  progressEditors[project.id] = { historyId:record.id, projectStatus:record.toStatus, effectiveOn:String(record.effectiveOn || '').replace('T',' ').slice(0,19), changeNote:record.changeNote || '', expectedUpdatedAt:record.updatedAt || record.changedAt }
}
function cancelProgressEdit(projectId) { delete progressEditors[projectId] }
async function saveProgress(project) {
  const editor = progressEditors[project.id]
  if (!editor?.effectiveOn) return ElMessage.warning('请选择节点时间')
  if (!editor.changeNote.trim()) return ElMessage.warning('请填写具体进度')
  setLoadingId(progressSavingIds, project.id, true)
  try {
    if (editor.historyId) {
      progressRows[project.id] = await annotationOpsApi.updateStatusHistoryProgress(editor.historyId, { effectiveOn:editor.effectiveOn, changeNote:editor.changeNote.trim(), expectedUpdatedAt:editor.expectedUpdatedAt })
    } else {
      await annotationApi.updateAnnotationProjectStatus(project.id, { projectStatus:editor.projectStatus, effectiveOn:editor.effectiveOn, changeNote:editor.changeNote.trim(), progressOnly:true })
      await loadProgress(project, true)
    }
    delete progressEditors[project.id]
    ElMessage.success('具体进度已保存')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '保存具体进度失败')) }
  finally { setLoadingId(progressSavingIds, project.id, false) }
}

async function confirmClose() {
  if (!hasDirtyChanges.value) return true
  try { await ElMessageBox.confirm('项目安排存在未保存修改，关闭后将丢失，是否继续？', '关闭项目安排', { type:'warning' }); return true } catch { return false }
}
async function beforeClose(done) { if (await confirmClose()) done() }
async function requestClose() { if (await confirmClose()) emit('update:modelValue', false) }

watch(
  () => [props.modelValue, props.initialProject?.id],
  ([visible, projectId]) => {
    if (visible && projectId) initialize()
  },
  { immediate:true },
)

onBeforeUnmount(() => { clearTimeout(searchTimer); searchController?.abort() })
</script>

<style scoped>
.arrangement-toolbar{display:flex;align-items:center;gap:10px;margin-bottom:14px}.project-search{width:min(620px,70vw)}.project-sort-select{width:190px}.toolbar-summary{margin-left:auto;color:var(--el-text-color-secondary);font-size:13px}.project-arrangement-list{display:grid;gap:16px}.project-arrangement-row{display:grid;grid-template-columns:minmax(240px,300px) minmax(0,1fr);align-items:start;gap:16px;padding:16px;border:1px solid var(--el-border-color-light);border-radius:10px;background:var(--el-fill-color-extra-light)}.project-summary-panel{position:sticky;top:0;align-self:start;min-width:0;padding:16px;border:1px solid var(--el-border-color-light);border-radius:8px;background:var(--el-bg-color);box-shadow:var(--el-box-shadow-lighter)}.project-sequence{margin-bottom:10px;color:var(--el-color-primary);font-size:13px;font-weight:600}.project-identity{display:grid;gap:5px;padding-bottom:13px;border-bottom:1px solid var(--el-border-color-lighter)}.project-identity strong,.project-identity span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.project-identity strong{font-size:15px}.project-identity span{color:var(--el-text-color-regular)}.project-summary-list{display:grid;gap:12px;margin:14px 0 0}.project-summary-list>div{display:grid;gap:4px;min-width:0}.project-summary-list dt{color:var(--el-text-color-secondary);font-size:12px}.project-summary-list dd{min-width:0;margin:0;color:var(--el-text-color-primary);font-size:13px}.project-summary-list dd[title]{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.project-task-summary{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.project-status-button{height:auto;padding:0}.remove-project-button{margin-top:12px}.project-arrangement-panel{min-width:0;padding:16px;border:1px solid var(--el-border-color-light);border-radius:8px;background:var(--el-bg-color)}.project-arrangement-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.project-arrangement-header>div:first-child{display:grid;gap:3px}.project-arrangement-header span{color:var(--el-text-color-secondary);font-size:12px}.project-arrangement-actions{display:flex;align-items:center;gap:8px;white-space:nowrap}.arrangement-task-table :deep(.el-form-item){margin:7px 0}.inline-progress-panel{margin:0 0 14px;padding:12px;border:1px solid var(--el-border-color-light);border-radius:6px;background:var(--el-fill-color-lighter)}.inline-progress-header{display:flex;align-items:center;gap:12px;margin-bottom:8px}.inline-progress-header span{color:var(--el-text-color-secondary);font-size:12px}.progress-groups{display:grid;gap:8px}.progress-group{padding:8px 10px;background:var(--el-bg-color);border-radius:5px}.progress-group__title{display:flex;align-items:center;gap:8px}.progress-items{margin-top:6px}.progress-item{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-top:1px dashed var(--el-border-color-lighter);white-space:pre-wrap}.progress-time{margin-right:8px;color:var(--el-text-color-secondary)}.muted{color:var(--el-text-color-placeholder);font-size:12px}.progress-editor{margin-top:12px;padding:12px;background:var(--el-bg-color);border-radius:5px}.progress-editor__actions{display:flex;justify-content:flex-end;gap:8px}.task-type-create{display:flex;gap:8px;margin-bottom:10px}.task-type-list{max-height:330px;overflow-y:auto}.task-type-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--el-border-color-lighter)}.task-type-row>span,.task-type-row>.el-input{flex:1}.task-type-actions{display:flex;white-space:nowrap}.is-inactive{text-decoration:line-through;color:var(--el-text-color-placeholder)}
:global(.annotation-arrangement-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.annotation-arrangement-dialog .el-dialog__header),:global(.annotation-arrangement-dialog .el-dialog__footer){flex:none}:global(.annotation-arrangement-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.annotation-arrangement-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
@media(max-width:900px){.arrangement-toolbar{align-items:stretch;flex-direction:column}.project-search,.project-sort-select{width:100%}.toolbar-summary{margin-left:0}.project-arrangement-row{grid-template-columns:minmax(0,1fr);padding:10px}.project-summary-panel{position:static}.project-arrangement-header{align-items:flex-start;flex-direction:column}.project-arrangement-actions{justify-content:space-between;width:100%}.project-task-summary{max-width:calc(100vw - 100px)}}
</style>
