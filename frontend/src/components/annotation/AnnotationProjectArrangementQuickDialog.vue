<template>
  <DraggableFormDialog
    :model-value="modelValue"
    width="min(920px, calc(100vw - 32px))"
    top="7vh"
    class="annotation-arrangement-quick-dialog"
    append-to-body
    destroy-on-close
    :modal="false"
    :lock-scroll="false"
    :close-on-click-modal="false"
    :before-close="beforeClose"
    @update:model-value="emit('update:modelValue', $event)"
    @open="initialize"
    @closed="resetState"
  >
    <template #header>
      <div class="quick-dialog-heading">
        <strong>项目安排</strong>
        <span @mousedown.stop>{{ textValue(activeProject?.orderNo) }}</span>
        <span class="heading-separator" aria-hidden="true" />
        <span class="heading-project" :title="textValue(activeProject?.projectName)" @mousedown.stop>
          {{ textValue(activeProject?.projectName) }}
        </span>
      </div>
    </template>

    <div class="quick-toolbar">
      <div>
        <strong>任务与安排</strong>
        <span>当前日期：{{ defaultDate }}</span>
      </div>
      <div class="quick-toolbar-actions">
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
                  <el-button :type="item.isActive ? 'warning' : 'success'" link size="small" @click="toggleTaskType(item)">
                    {{ item.isActive ? '停用' : '恢复' }}
                  </el-button>
                </div>
              </div>
              <el-empty v-if="!taskTypes.length" description="暂无任务类型" :image-size="52" />
            </div>
          </div>
        </el-popover>
        <el-button v-if="canWrite && allowNewTasks" type="primary" plain @click="addTask">新增任务</el-button>
      </div>
    </div>

    <AppForm ref="formRef" :model="formModel" label-position="top" class="quick-arrangement-form">
      <el-table :data="formModel.tasks" border size="small" class="quick-task-table">
        <el-table-column prop="executionDate" label="执行日期" width="158">
          <template #default="{ row, $index }">
            <el-form-item :prop="taskProp($index, 'executionDate')" :rules="requiredRule('请选择执行日期', 'change')">
              <el-date-picker v-model="row.executionDate" type="date" value-format="YYYY-MM-DD" style="width:100%" :disabled="!canWrite" @change="markDirty(row)" />
            </el-form-item>
          </template>
        </el-table-column>
        <el-table-column prop="taskTypeId" label="任务类型" min-width="180">
          <template #default="{ row, $index }">
            <el-form-item :prop="taskProp($index, 'taskTypeId')" :rules="requiredRule('请选择任务类型', 'change')">
              <el-select v-model="row.taskTypeId" filterable allow-create default-first-option style="width:100%" :disabled="!canWrite" @change="(value) => selectTaskType(row, value)">
                <el-option v-for="item in taskTypeOptions(row)" :key="item.id" :label="item.isActive ? item.name : `${item.name}（已停用）`" :value="item.id" :disabled="!item.isActive && item.id !== row.originalTaskTypeId" />
              </el-select>
            </el-form-item>
          </template>
        </el-table-column>
        <el-table-column prop="assigneeId" label="执行人" min-width="180">
          <template #default="{ row, $index }">
            <el-form-item :prop="taskProp($index, 'assigneeId')" :rules="requiredRule('请选择执行人', 'change')">
              <el-select v-model="row.assigneeId" filterable style="width:100%" :disabled="!canWrite" @change="markDirty(row)">
                <el-option-group v-for="group in assigneeGroups" :key="group.key" :label="group.label">
                  <el-option v-for="person in group.options" :key="person.id" :label="person.department ? `${person.displayName}（${person.department}）` : person.displayName" :value="person.id" />
                </el-option-group>
              </el-select>
            </el-form-item>
          </template>
        </el-table-column>
        <el-table-column label="任务内容" min-width="300">
          <template #default="{ row, $index }">
            <el-form-item :prop="taskProp($index, 'taskContent')" :rules="requiredRule('请填写任务内容', 'blur')">
              <el-input v-model="row.taskContent" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" maxlength="10000" show-word-limit :disabled="!canWrite" @input="markDirty(row)" />
            </el-form-item>
          </template>
        </el-table-column>
        <el-table-column v-if="canWrite" label="操作" width="68" fixed="right" align="center">
          <template #default="{ row }"><el-button type="danger" link size="small" @click="removeTask(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-empty v-if="initialized && !formModel.tasks.length" description="暂无项目安排" :image-size="56" />
    </AppForm>

    <template #footer>
      <el-button @click="requestClose">取消</el-button>
      <el-button v-if="canWrite" type="primary" :loading="saving" @click="saveAll">保存</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as annotationOpsApi from '@/api/annotationOps'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialProject: { type: Object, default: null },
  defaultExecutionDate: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
  allowNewTasks: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'saved', 'project-change-rejected'])

const formRef = ref(null)
const formModel = reactive({ tasks: [] })
const activeProject = ref(null)
const taskTypes = ref([])
const assignees = ref([])
const deletedItems = ref([])
const saving = ref(false)
const initialized = ref(false)
const switching = ref(false)
const newTaskTypeName = ref('')
const editingTaskTypeId = ref('')
const editingTaskTypeName = ref('')
const taskTypeSaving = ref(false)
let newTaskSequence = 0

const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
const requiredRule = (message, trigger) => [{ required:true, message, trigger }]
const tomorrowString = (now = new Date()) => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone:'Asia/Hong_Kong', year:'numeric', month:'2-digit', day:'2-digit',
  }).formatToParts(now).filter(item => item.type !== 'literal').map(item => [item.type,item.value]))
  const date = new Date(Date.UTC(Number(parts.year), Number(parts.month)-1, Number(parts.day)+1))
  return date.toISOString().slice(0,10)
}
const defaultDate = computed(() => /^\d{4}-\d{2}-\d{2}$/.test(props.defaultExecutionDate) ? props.defaultExecutionDate : tomorrowString())
const hasDirtyChanges = computed(() => deletedItems.value.length > 0 || formModel.tasks.some(task => task._dirty || !task.id))
const assigneeGroups = computed(() => [
  { key:'project_manager', label:'项目经理', options:assignees.value.filter(item => item.priorityGroup === 'project_manager') },
  { key:'hr', label:'HR', options:assignees.value.filter(item => item.priorityGroup === 'hr') },
  { key:'other', label:'其他员工', options:assignees.value.filter(item => item.priorityGroup === 'other') },
].filter(group => group.options.length))

const normalizeTask = (task) => ({
  ...task,
  _key:task.id || `new-${++newTaskSequence}`,
  expectedUpdatedAt:task.updatedAt || null,
  originalTaskTypeId:task.taskTypeId || '',
  _dirty:false,
})
const taskProp = (index, field) => `tasks.${index}.${field}`
const markDirty = (task) => { task._dirty = true }
const taskTypeOptions = (task) => taskTypes.value.filter(item => item.isActive || item.id === task.originalTaskTypeId)

function addTask() {
  if (!props.allowNewTasks) return
  formModel.tasks.push(normalizeTask({
    projectId:activeProject.value?.id,
    executionDate:defaultDate.value,
    taskTypeId:'', assigneeId:'', taskContent:'',
  }))
}

function removeTask(task) {
  if (task.id) deletedItems.value.push({ id:task.id, expectedUpdatedAt:task.expectedUpdatedAt })
  formModel.tasks.splice(formModel.tasks.indexOf(task), 1)
}

async function loadProject(project) {
  const context = await annotationOpsApi.getProjectArrangementContext([project.id])
  const loaded = context.projects?.[0]
  if (!loaded) throw new Error('标注项目不存在或已被删除')
  activeProject.value = { ...project, ...loaded }
  taskTypes.value = context.taskTypes || []
  assignees.value = context.assignees || []
  formModel.tasks.splice(0, formModel.tasks.length, ...(loaded.tasks || []).map(normalizeTask))
  deletedItems.value = []
  if (props.canWrite && props.allowNewTasks && !formModel.tasks.length) addTask()
  initialized.value = true
}

async function initialize() {
  if (initialized.value || !props.initialProject?.id) return
  try { await loadProject(props.initialProject) }
  catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '加载项目安排失败')) }
}

function resetState() {
  formModel.tasks.splice(0)
  activeProject.value = null
  taskTypes.value = []
  assignees.value = []
  deletedItems.value = []
  initialized.value = false
  switching.value = false
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
    Object.assign(item, await annotationOpsApi.updateArrangementTaskType(item.id, { name, expectedUpdatedAt:item.updatedAt }))
    editingTaskTypeId.value = ''
    ElMessage.success('任务类型已更新')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '更新任务类型失败')) }
  finally { taskTypeSaving.value = false }
}

async function toggleTaskType(item) {
  try {
    Object.assign(item, await annotationOpsApi.setArrangementTaskTypeState(item.id, { isActive:!item.isActive, expectedUpdatedAt:item.updatedAt }))
    ElMessage.success(item.isActive ? '任务类型已恢复' : '任务类型已停用')
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '更新任务类型状态失败')) }
}

async function saveAll(closeAfterSave = false) {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return false
  saving.value = true
  try {
    await annotationOpsApi.saveProjectArrangements({
      items:formModel.tasks.map(task => ({
        id:task.id || undefined,
        projectId:activeProject.value.id,
        executionDate:task.executionDate,
        taskTypeId:task.taskTypeId,
        assigneeId:task.assigneeId,
        taskContent:task.taskContent.trim(),
        expectedUpdatedAt:task.expectedUpdatedAt,
      })),
      deletedItems:deletedItems.value.map(item => ({ id:item.id, expectedUpdatedAt:item.expectedUpdatedAt })),
    })
    await loadProject(activeProject.value)
    ElMessage.success('项目安排已保存')
    emit('saved')
    if (closeAfterSave) emit('update:modelValue', false)
    return true
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '保存项目安排失败'))
    return false
  } finally { saving.value = false }
}

async function resolveDirtyBeforeSwitch() {
  if (!hasDirtyChanges.value) return 'discard'
  try {
    await ElMessageBox.confirm('当前项目存在未保存修改，请选择处理方式。', '切换安排项目', {
      type:'warning',
      confirmButtonText:'保存并切换',
      cancelButtonText:'放弃并切换',
      distinguishCancelAndClose:true,
    })
    return await saveAll() ? 'save' : 'stay'
  } catch (action) {
    return action === 'cancel' ? 'discard' : 'stay'
  }
}

async function switchProject(project) {
  if (!project?.id || project.id === activeProject.value?.id || switching.value) return
  switching.value = true
  const previous = activeProject.value
  try {
    const decision = await resolveDirtyBeforeSwitch()
    if (decision === 'stay') {
      emit('project-change-rejected', previous)
      return
    }
    initialized.value = false
    await loadProject(project)
  } catch (error) {
    emit('project-change-rejected', previous)
    ElMessage.error(getLocalizedErrorMessage(error, '切换安排项目失败'))
  } finally { switching.value = false }
}

async function confirmClose() {
  if (!hasDirtyChanges.value) return true
  try {
    await ElMessageBox.confirm('项目安排存在未保存修改，关闭后将丢失，是否继续？', '关闭项目安排', { type:'warning' })
    return true
  } catch { return false }
}
async function beforeClose(done) { if (await confirmClose()) done() }
async function requestClose() { if (await confirmClose()) emit('update:modelValue', false) }

watch(() => props.initialProject?.id, () => {
  if (props.modelValue && props.initialProject?.id) {
    if (!initialized.value) initialize()
    else switchProject(props.initialProject)
  }
})
</script>

<style scoped>
.quick-dialog-heading{display:flex;align-items:center;gap:10px;min-width:0;padding-right:28px}.quick-dialog-heading>span{user-select:text;cursor:text}.heading-separator{width:1px;height:18px;background:var(--el-border-color)}.heading-project{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--el-text-color-regular)}.quick-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px}.quick-toolbar>div:first-child{display:grid;gap:3px}.quick-toolbar>div:first-child span{color:var(--el-text-color-secondary);font-size:12px}.quick-toolbar-actions{display:flex;gap:8px;flex:none}.quick-task-table :deep(.el-form-item){margin:7px 0}.task-type-create{display:flex;gap:8px;margin-bottom:10px}.task-type-list{max-height:330px;overflow-y:auto}.task-type-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--el-border-color-lighter)}.task-type-row>span,.task-type-row>.el-input{flex:1}.task-type-actions{display:flex;white-space:nowrap}.is-inactive{text-decoration:line-through;color:var(--el-text-color-placeholder)}
:global(.annotation-arrangement-quick-dialog){display:flex;flex-direction:column;max-height:86vh;overflow:hidden;background:#fff;box-shadow:0 18px 48px rgb(15 23 42 / 22%)}:global(.annotation-arrangement-quick-dialog .el-dialog__header),:global(.annotation-arrangement-quick-dialog .el-dialog__footer){flex:none}:global(.annotation-arrangement-quick-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.annotation-arrangement-quick-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
@media(max-width:760px){.quick-toolbar{align-items:stretch;flex-direction:column}.quick-toolbar-actions{justify-content:space-between}.quick-task-table{min-width:760px}.quick-arrangement-form{overflow-x:auto}}
</style>
