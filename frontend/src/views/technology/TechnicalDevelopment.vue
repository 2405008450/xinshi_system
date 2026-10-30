<template>
  <el-config-provider :z-index="props.dialogOnly ? 100004 : undefined">
  <el-card v-show="!props.dialogOnly" class="common-page-card technical-development" shadow="never">
    <template #header>
      <div class="page-header">
        <span class="page-title">技术开发</span>
        <div class="actions">
          <TableColumnSettings v-if="!deleteMode" v-model="columnKeys" :columns="columns" settings-key="technical-development" @reset="resetColumns" />
          <BatchDeleteToolbar :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="deleteSelected" />
          <el-button :loading="loading" :disabled="deleting" @click="load">刷新</el-button>
          <el-button v-if="!deleteMode" type="primary" :disabled="!enabled" @click="openEditor()">新增任务</el-button>
        </div>
      </div>
    </template>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="notice" />
    <el-alert v-if="!enabled && !loading" title="技术开发数据表尚未初始化" type="warning" :closable="false" class="notice" />
    <div class="filters">
      <el-input v-model="keyword" clearable placeholder="任务编号、任务名称、具体任务、安排人、执行人、调整、备注" aria-label="搜索技术开发任务" @keyup.enter="search" />
      <el-button @click="search">查询</el-button><el-button @click="keyword = ''; search()">重置</el-button>
    </div>
    <div class="tree-help" :class="{ 'is-dragging': draggingId }" @dragover.prevent @drop.prevent="dropTask(null)">
      拖动任务名称前的 ⠿ 到另一任务名称上，成为其子任务；拖到此处恢复为一级任务。最多支持三级。
    </div>
    <el-table ref="tableRef" @selection-change="handleDeleteSelectionChange" v-loading="loading || moving || deleting" :key="appliedKeyword" :data="tree" row-key="id" border default-expand-all :tree-props="{ children: 'children', checkStrictly: true }">
      <el-table-column v-if="deleteMode" type="selection" width="48" />
      <el-table-column v-if="isVisible('task_no')" label="任务编号" min-width="230"><template #default="{ row }">
          <el-popover trigger="click" placement="left" :width="760" title="技术开发任务详情" @before-enter="loadDetail(row.id)">
            <template #reference><el-button link type="primary">{{ row.task_no }}</el-button></template>
            <div v-loading="detailLoading" class="task-detail">
              <el-alert v-if="detailError" :title="detailError" type="error" :closable="false" />
              <el-descriptions v-if="detail?.id === row.id" :column="2" border size="small">
                <el-descriptions-item v-for="item in detailFields" :key="item.label" :label="item.label">{{ item.value || '-' }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
      </template></el-table-column>
      <el-table-column v-if="!isVisible('name')" label="层级" width="100"><template #default="{ row }">{{ row.level }}级</template></el-table-column>
      <el-table-column v-if="isVisible('name')" label="任务名称" min-width="290">
        <template #default="{ row }">
          <span class="task-name" :class="{ 'drop-target': dropTarget === row.id }" @dragover.prevent="dropTarget = row.id" @dragleave="dropTarget = null" @drop.stop.prevent="dropTask(row.id)">
            <button class="drag-handle" draggable="true" :disabled="moving || deleteMode" :aria-label="`拖动任务：${row.name}`" title="拖动调整任务层级" @dragstart="startDrag($event, row)" @dragend="endDrag">⠿</button>
            <span>{{ row.name }}</span>
            <el-tag v-if="row.level > 1" size="small" type="info">{{ row.level === 2 ? '子任务' : '三级任务' }}</el-tag>
          </span>
        </template>
      </el-table-column>
      <el-table-column v-if="isVisible('content')" prop="content" label="具体任务" min-width="230" show-overflow-tooltip />
      <el-table-column v-if="isVisible('arranger')" prop="arranger_name" label="安排人" width="110" />
      <el-table-column v-if="isVisible('executor')" label="执行人" min-width="180"><template #default="{ row }">{{ row.executor_name }}<el-button v-if="row.has_allocations" link type="primary" @click="allocationViewerId = row.id">分工与完成情况</el-button></template></el-table-column>
      <el-table-column v-if="isVisible('due_at')" label="预定完成时间" width="185"><template #default="{ row }">{{ formatTime(row.due_at) }}</template></el-table-column>
      <el-table-column v-if="isVisible('completed_on')" label="完成日期" min-width="220"><template #default="{ row }"><el-button v-if="row.has_allocations" link type="primary" @click="allocationViewerId = row.id">按分工分别记录</el-button><el-date-picker v-else :ref="control => { if (control) completionPickers.set(row.id, control); else completionPickers.delete(row.id) }" :model-value="row.completed_on" type="date" value-format="YYYY-MM-DD" :automatic-dropdown="false" :disabled="!row.due_at || !row.completion_enabled" :placeholder="row.due_at ? '选择完成日期' : '请先设置预定完成时间'" @update:model-value="value => requestCompletionDate(row, value)" /><TaskCompletionHistory :task-id="row.id" /></template></el-table-column>
      <el-table-column v-if="isVisible('on_time')" label="是否按时完成" min-width="190"><template #default="{ row }"><el-button v-if="row.has_allocations" link type="primary" @click="allocationViewerId = row.id">按人分别计算</el-button><span v-else-if="row.on_time == null">待完成</span><el-button v-else link :type="row.on_time ? 'success' : 'warning'" @click="completionEditor = { taskId: row.id, mode: 'amount' }">{{ row.on_time ? '是 · 给予奖励' : '否 · 抵消奖金' }}</el-button><small v-if="row.on_time != null">{{ row.incentive ? `当前金额：${row.incentive.amount}` : '待登记金额' }}</small></template></el-table-column>
      <el-table-column v-if="isVisible('progress')" label="具体进度" min-width="220">
        <template #default="{ row }">
          <button class="progress-button" :aria-label="`${row.name}：进度 ${row.progress}%，查看和修改进度`" @click="openActivity(row, 'progress')"><el-progress :percentage="row.progress" /><small>修改于：{{ formatTime(row.progress_updated_at) }}</small></button>
        </template>
      </el-table-column>
      <el-table-column v-if="isVisible('feedback')" label="反馈意见" width="140"><template #default="{ row }"><el-button link type="primary" @click="openActivity(row, 'feedback')">查看 / 填写反馈</el-button></template></el-table-column>
      <el-table-column v-if="isVisible('adjustment')" prop="adjustment" label="反馈后调整" min-width="200" show-overflow-tooltip />
      <el-table-column v-if="isVisible('notes')" prop="notes" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="!deleteMode" label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <ProjectListRowActions
            edit-in-more
            :show-start-request="false"
            :extra-actions="taskActions(row)"
            @edit="openEditor(row)"
            @extra-command="command => handleTaskAction(command, row)"
          />
        </template>
      </el-table-column>
    </el-table>
    <div class="count">共 {{ rows.length }} 个任务，当前显示 {{ visibleCount }} 个（含子任务）</div>

    <DraggableFormDialog v-model="editorVisible" :title="editing ? '编辑技术开发任务' : '新增技术开发任务'" class="technical-task-dialog" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body :before-close="closeEditor" :close-on-click-modal="false" @closed="props.dialogOnly && emit('close')">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editing ? '编辑技术开发任务' : '新增技术开发任务'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editorBody">
        <AppForm ref="editorForm" :model="form" :rules="rules" label-position="top" class="task-form">
          <el-form-item label="任务编号" class="full"><ReadonlyField :model-value="editing?.task_no || '保存后自动生成'" source="auto" /></el-form-item>
          <el-form-item :label="sourceBaseName ? '开发任务' : '任务名称'" prop="name" class="full"><template v-if="sourceBaseName"><ReadonlyField :model-value="sourceBaseName" source="auto" /><el-input v-model="sourceSuffix" maxlength="80" show-word-limit placeholder="可在项目名称后补充内容，最多80字" aria-label="任务名称补充内容" /></template><el-input v-else v-model="form.name" maxlength="300" show-word-limit /></el-form-item>
          <el-form-item label="上级任务" class="full"><el-select v-model="form.parent_id" clearable filterable placeholder="一级任务（无上级）" :disabled="!!editing"><el-option v-for="option in parentOptions" :key="option.id" :value="option.id" :label="option.name" /></el-select><small v-if="editing">调整层级请使用列表拖拽，或下方“调整层级”。</small></el-form-item>
          <el-form-item label="具体任务" class="full"><el-input v-model="form.content" type="textarea" :rows="4" maxlength="100000" /></el-form-item>
          <el-form-item label="安排人" prop="arranger_id"><el-select v-model="form.arranger_id" filterable placeholder="公司全体人员"><el-option v-for="person in arrangerOptions" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
          <el-form-item label="执行人" prop="executor_id"><el-select ref="executorSelect" v-model="selectedExecutorIds" multiple filterable placeholder="技术部全体人员，可多选" @change="executorsChanged"><el-option v-for="person in executorOptions" :key="person.id" :value="person.id" :label="person.name" /></el-select><el-button v-if="selectedExecutorIds.length > 1 || editing?.has_allocations" link type="primary" @click="allocationEditorVisible = true">设置分工</el-button></el-form-item>
          <el-form-item label="预定完成时间" class="full"><el-date-picker v-model="form.due_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="按香港时间选择" /></el-form-item>
          <el-form-item v-if="editing" label="完成日期" class="full"><ReadonlyField :model-value="editing.has_allocations ? '按分工分别记录' : editing.completed_on || '待完成'" source="auto" /><el-button link type="primary" @click="editing.has_allocations ? allocationViewerId = editing.id : completionEditor = { taskId: editing.id, mode: 'date' }">调整完成日期</el-button></el-form-item>
          <el-form-item label="反馈后调整" class="full"><el-input v-model="form.adjustment" type="textarea" :rows="4" maxlength="30000" /></el-form-item>
          <el-form-item label="备注" class="full"><el-input v-model="form.notes" type="textarea" :rows="3" maxlength="30000" /></el-form-item>
        </AppForm>
      </div>
      <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><el-button :disabled="saving" @click="editorVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveTask">保存</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="activityVisible" :title="activityMode === 'progress' ? '任务进度与修改记录' : '任务反馈意见'" class="technical-task-dialog" width="min(820px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="closeActivity">
      <div v-loading="activityLoading">
        <el-alert v-if="activityError" :title="activityError" type="error" :closable="false" class="notice" />
        <template v-if="activity">
          <p class="activity-name">{{ activity.name }}</p>
          <template v-if="activityMode === 'progress'">
            <el-progress :percentage="activity.progress" />
            <AppForm ref="progressForm" :model="progress" :rules="progressRules" label-position="top">
              <el-form-item label="进度（1—100）" prop="percentage"><el-input-number v-model="progress.percentage" :min="1" :max="100" :precision="0" /></el-form-item>
              <el-form-item label="具体进度" prop="content"><el-input v-model="progress.content" type="textarea" :rows="3" maxlength="30000" /></el-form-item>
              <el-form-item label="修改原因" prop="reason"><el-input v-model="progress.reason" type="textarea" :rows="2" maxlength="3000" :placeholder="progress.percentage < activity.progress ? '进度回退必须填写修改原因' : '可填写本次修改原因'" /></el-form-item>
            </AppForm>
            <h4>进度修改记录</h4>
            <el-empty v-if="!activity.progress_history.length" description="暂无修改记录" :image-size="60" />
            <article v-for="record in activity.progress_history" :key="record.id" class="history-record"><div><strong>{{ record.previous_percentage }}% → {{ record.percentage }}%</strong><span>{{ record.author_name }} · {{ formatTime(record.created_at) }}</span></div><p v-if="record.content">{{ record.content }}</p><p v-if="record.reason">修改原因：{{ record.reason }}</p></article>
          </template>
          <template v-else>
            <AppForm ref="feedbackForm" :model="feedback" :rules="feedbackRules" label-position="top"><el-form-item label="反馈意见" prop="content"><el-input v-model="feedback.content" type="textarea" :rows="4" maxlength="30000" placeholder="填写反馈意见，保存后自动记录反馈人和时间" /></el-form-item></AppForm>
            <h4>全部反馈意见</h4>
            <el-empty v-if="!activity.feedback.length" description="暂无反馈意见" :image-size="60" />
            <article v-for="record in activity.feedback" :key="record.id" class="history-record"><div><strong>{{ record.author_name }}</strong><span>{{ formatTime(record.created_at) }}</span></div><p>{{ record.content }}</p></article>
          </template>
        </template>
      </div>
      <template #footer><el-button :disabled="saving" @click="activityVisible = false">关闭</el-button><el-button type="primary" :loading="saving" :disabled="activityLoading || !activity" @click="saveActivity">{{ activityMode === 'progress' ? '保存进度' : '提交反馈' }}</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="moveVisible" title="调整任务层级" width="min(600px, calc(100vw - 32px))" :before-close="closeMove">
      <p>{{ moveRow?.name }}</p><el-select v-model="moveParent" clearable filterable placeholder="一级任务（无上级）" style="width:100%"><el-option v-for="item in moveOptions" :key="item.id" :value="item.id" :label="item.name" /></el-select>
      <template #footer><el-button :disabled="moving" @click="moveVisible = false">取消</el-button><el-button type="primary" :loading="moving" @click="performMove(moveRow, moveParent)">确定</el-button></template>
    </DraggableFormDialog>
    <el-dropdown v-if="rows.length && !deleteMode" class="move-entry" @command="openMove"><el-button>调整层级（选择任务）</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="row in rows" :key="row.id" :command="row.id">{{ row.name }}</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
    <DraggableFormDialog v-model="swapVisible" title="互换任务位置" class="technical-task-dialog" width="min(600px, calc(100vw - 32px))" :before-close="closeMove">
      <p>将 {{ swapRow?.task_no }} {{ swapRow?.name }} 与下方任务互换位置。任务内容、进度和记录跟随原任务，编号按新位置调整。</p>
      <el-select v-model="swapTarget" filterable placeholder="选择要互换的任务" style="width:100%"><el-option v-for="item in rows.filter(item => item.id !== swapRow?.id)" :key="item.id" :value="item.id" :label="item.task_no + ' ' + item.name" /></el-select>
      <template #footer><el-button :disabled="moving" @click="swapVisible = false">取消</el-button><el-button type="primary" :loading="moving" :disabled="!swapTarget" @click="swapTasks">确认互换</el-button></template>
    </DraggableFormDialog>
    <DevelopmentReportDialog v-if="reportTaskId" :task-id="reportTaskId" @close="reportTaskId = null" />
    <TaskAllocationEditor v-if="allocationEditorVisible" :people="executorOptions" :selected="selectedExecutorIds" :allocations="allocationDrafts" :default-due="form.due_at" @cancel="cancelAllocations" @confirmed="confirmAllocations" />
    <TaskAllocationViewer v-if="allocationViewerTask" :task="allocationViewerTask" @close="allocationViewerId = null" @changed="load" />
    <TaskCompletionEditor v-if="completionEditor" :key="completionEditor.taskId + ':' + completionEditor.mode" :task-id="completionEditor.taskId" :initial-mode="completionEditor.mode" :initial-date="completionEditor.date" @close="completionEditor = null" @changed="completionChanged" />
  </el-card>
  </el-config-provider>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import DevelopmentReportDialog from './DevelopmentReportDialog.vue'
import TaskCompletionEditor from './TaskCompletionEditor.vue'
import TaskCompletionHistory from './TaskCompletionHistory.vue'
import TaskAllocationEditor from './TaskAllocationEditor.vue'
import TaskAllocationViewer from './TaskAllocationViewer.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useTableColumns } from '@/composables/useTableColumns'
import { formatBusinessDateTimeMinute as formatTime, businessDateTimeInputValue } from '@/utils/dateTime'
import { canMoveTask, taskTree } from '@/utils/technicalDevelopment'
import * as api from '@/api/technicalDevelopment'
import { useRoute, useRouter } from 'vue-router'
import { getRequirementTask, saveRequirementTask } from '@/api/technicalRequirementTasks'
import { generateFeedbackSheet } from '@/api/developmentFeedback'

const props = defineProps({ dialogOnly: Boolean, initialContent: { type: String, default: '' } })
const emit = defineEmits(['close', 'saved'])

function taskActions(row) {
  return [
    ...(row.level < 3 ? [{ command: 'add-child', label: '添加子任务' }] : []),
    { command: 'swap-position', label: '互换位置' },
    { command: 'add-report', label: '加至工作报告' },
    { command: 'generate-feedback', label: generatingFeedback.value === row.id ? '生成反馈表中…' : '生成反馈表', disabled: !!generatingFeedback.value },
  ]
}

function handleTaskAction(command, row) {
  if (command === 'add-child') openEditor(null, row)
  else if (command === 'swap-position') { swapRow.value = row; swapTarget.value = null; swapVisible.value = true }
  else if (command === 'add-report') openTaskReport(row)
  else if (command === 'generate-feedback' && !generatingFeedback.value) generateFeedback(row)
}
const router = useRouter(), route = useRoute(), generatingFeedback = ref('')
async function generateFeedback(row) {
  if (generatingFeedback.value) return
  generatingFeedback.value = row.id
  try { await generateFeedbackSheet(row.id); await router.push({ name: 'DevelopmentFeedback', query: { taskId: row.id } }) }
  catch (e) { ElMessage.error(message(e, '生成反馈表失败')) }
  finally { generatingFeedback.value = '' }
}

const rows = ref([]), loading = ref(false), enabled = ref(true), error = ref(''), keyword = ref(''), appliedKeyword = ref('')
const people = reactive({ arrangers: [], executors: [] })
const reportTaskId = ref(null)
const completionEditor = ref(null)
const allocationViewerId = ref(null)
const allocationViewerTask = computed(() => rows.value.find(row => row.id === allocationViewerId.value))
function openTaskReport(row) {
  if (!row.has_allocations) { reportTaskId.value = row.id; return }
  const mine = row.allocations.find(item => item.executor_id === localStorage.getItem('user_id'))
  if (mine) reportTaskId.value = mine.task_id
  else allocationViewerId.value = row.id
}
const completionPickers = new Map()
function requestCompletionDate(row, value) {
  if (value === row.completed_on) return
  completionPickers.get(row.id)?.handleClose?.()
  completionPickers.get(row.id)?.blur?.()
  completionEditor.value = { taskId: row.id, mode: 'date', date: value }
}
function completionChanged(value) {
  const fields = Object.fromEntries(['completed_on', 'on_time', 'completion_revision', 'incentive'].map(key => [key, value[key]]))
  const row = rows.value.find(row => row.id === value.task_id)
  if (row) Object.assign(row, fields)
  if (editing.value?.id === value.task_id) Object.assign(editing.value, fields)
  detail.value = null
  void load()
}
const columns = [{ key: 'task_no', label: '任务编号' }, { key: 'name', label: '任务名称' }, { key: 'content', label: '具体任务' }, { key: 'arranger', label: '安排人' }, { key: 'executor', label: '执行人' }, { key: 'due_at', label: '预定完成时间' }, { key: 'completed_on', label: '完成日期' }, { key: 'on_time', label: '是否按时完成' }, { key: 'progress', label: '具体进度' }, { key: 'feedback', label: '反馈意见' }, { key: 'adjustment', label: '反馈后调整' }, { key: 'notes', label: '备注' }]
const { selectedKeys: columnKeys, isVisible, reset: resetColumns } = useTableColumns('technical-development', columns, ['task_no', 'name', 'content', 'arranger', 'executor', 'due_at', 'completed_on', 'on_time', 'progress', 'feedback'], { legacyDefaultKeys: [['name', 'content', 'arranger', 'executor', 'due_at', 'progress', 'feedback'], ['task_no', 'name', 'content', 'arranger', 'executor', 'due_at', 'progress', 'feedback']] })
const tree = computed(() => taskTree(rows.value, appliedKeyword.value))
const tableRef = ref(null)
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({
  rows: () => { const flatten = nodes => nodes.flatMap(row => [row, ...flatten(row.children || [])]); return flatten(tree.value) },
  tableRef, entityName: '开发任务', getLabel: row => `${row.task_no} ${row.name}`,
  deleteRow: row => api.deleteDevelopmentTask(row.id, row.revision), reload: load,
  onDeleted: () => { detail.value = null },
})
function deleteSelected() { selectedRows.value.sort((a,b) => b.level-a.level); return confirmBatchDelete() }
const swapVisible = ref(false), swapRow = ref(null), swapTarget = ref(null)
async function swapTasks() {
  const target = rows.value.find(item => item.id === swapTarget.value)
  if (!target || moving.value) return
  moving.value = true
  try { await api.swapDevelopmentTasks(swapRow.value.id, { target_id: target.id, revision: swapRow.value.revision, target_revision: target.revision }); swapVisible.value = false; detail.value = null; await load(); ElMessage.success('任务位置已互换') }
  catch(e) { ElMessage.error(message(e, '互换失败，请刷新后重试')) }
  finally { moving.value = false }
}

const countNodes = items => items.reduce((count, item) => count + 1 + countNodes(item.children), 0)
const visibleCount = computed(() => countNodes(tree.value))
let controller, sequence = 0, timer, alive = true
const message = (e, fallback) => typeof e?.detail === 'string' ? e.detail : e?.message || fallback
async function load() {
  const current = ++sequence
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { const result = await api.getDevelopmentTasks(controller.signal); if (alive && current === sequence) { rows.value = result.items; enabled.value = result.enabled } }
  catch (e) { if (alive && current === sequence && e.code !== 'ERR_CANCELED') error.value = message(e, '加载任务失败') }
  finally { if (alive && current === sequence) loading.value = false }
}
function search() { if (deleting.value) return; if (deleteMode.value) exitDeleteMode(); clearTimeout(timer); appliedKeyword.value = keyword.value }
watch(keyword, value => { clearTimeout(timer); if (!value) search(); else timer = setTimeout(search, 400) })
async function loadPeople() { Object.assign(people, await api.getDevelopmentPeople()) }
onMounted(async () => {
  load()
  if (props.dialogOnly) { openEditor(); form.content = props.initialContent; return }
  try { await loadPeople() } catch (e) { error.value = message(e, '人员目录加载失败') }
})
onBeforeUnmount(() => { alive = false; sequence++; controller?.abort(); clearTimeout(timer) })

const editorVisible = ref(false), editing = ref(null), editorForm = ref(null), editorBody = ref(null), saving = ref(false), saveError = ref('')
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(editorBody)
const form = reactive({ name: '', parent_id: null, content: '', arranger_id: '', executor_id: '', due_at: '', adjustment: '', notes: '' })
const requirementContext = ref(null), sourceSuffix = ref('')
const selectedExecutorIds = ref([]), allocationDrafts = ref([]), confirmedExecutorIds = ref([]), allocationEditorVisible = ref(false), executorSelect = ref(null)
function executorsChanged(ids) {
  if (ids.length > 1 || editing.value?.has_allocations) { executorSelect.value?.blur?.(); allocationEditorVisible.value = true; return }
  form.executor_id = ids[0] || ''; confirmedExecutorIds.value = [...ids]; allocationDrafts.value = []
}
function confirmAllocations(items) { allocationDrafts.value = items; selectedExecutorIds.value = items.map(item => item.executor_id); confirmedExecutorIds.value = [...selectedExecutorIds.value]; form.executor_id = selectedExecutorIds.value[0] || ''; allocationEditorVisible.value = false }
function cancelAllocations() { selectedExecutorIds.value = [...confirmedExecutorIds.value]; form.executor_id = selectedExecutorIds.value[0] || ''; allocationEditorVisible.value = false }
const sourceBaseName = computed(() => requirementContext.value?.source_name || editing.value?.source?.base_name || '')
const rules = { name: [{ required: true, whitespace: true, message: '请填写任务名称', trigger: 'blur' }], arranger_id: [{ required: true, message: '请选择安排人', trigger: 'change' }], executor_id: [{ required: true, message: '请选择执行人', trigger: 'change' }] }
const parentOptions = computed(() => rows.value.filter(row => canMoveTask(rows.value, '__new__', row.id) && (!row.parent_id || !rows.value.find(parent => parent.id === row.parent_id)?.parent_id)))
function historicalOptions(options, key, nameKey) { const row = editing.value; return row && !options.some(person => person.id === row[key]) ? [...options, { id: row[key], name: row[nameKey] + '（原人员）' }] : options }
const arrangerOptions = computed(() => historicalOptions(people.arrangers, 'arranger_id', 'arranger_name'))
const executorOptions = computed(() => { const values = [...(editing.value?.has_allocations ? people.executors : historicalOptions(people.executors, 'executor_id', 'executor_name'))]; for (const item of editing.value?.allocations || []) if (!values.some(person => person.id === item.executor_id)) values.push({ id:item.executor_id, name:item.executor_name + '（原人员）' }); return values })
function openEditor(row = null, parent = null) {
  requirementContext.value = null; sourceSuffix.value = row?.source?.suffix || ''
  editing.value = row; saveError.value = ''; clearFieldSearch()
  Object.assign(form, { name: row?.name || '', parent_id: row?.parent_id || parent?.id || null, content: row?.content || '', arranger_id: row?.arranger_id || '', executor_id: row?.executor_id || '', due_at: row?.due_at ? businessDateTimeInputValue(row.due_at) : '', adjustment: row?.adjustment || '', notes: row?.notes || '' })
  selectedExecutorIds.value = row?.has_allocations ? row.allocations.map(item => item.executor_id) : row?.executor_id ? [row.executor_id] : []
  confirmedExecutorIds.value = [...selectedExecutorIds.value]
  allocationDrafts.value = (row?.allocations || (row ? [row] : [])).map(item => ({ executor_id:item.executor_id, content:item.content, due_at:item.due_at ? businessDateTimeInputValue(item.due_at) : '', completed_on:item.completed_on }))
  editorVisible.value = true; loadPeople().catch(e => { saveError.value = message(e, '人员目录加载失败') })
}
function closeEditor(done) { if (!saving.value) done() }
async function saveTask() {
  if (saving.value || !await editorForm.value.validate().catch(() => false)) return
  saving.value = true; saveError.value = ''
  const { parent_id, ...fields } = form
  const payload = { ...fields, name: sourceBaseName.value ? sourceBaseName.value + (sourceSuffix.value.trim() ? ' · ' + sourceSuffix.value.trim() : '') : fields.name, due_at: fields.due_at ? fields.due_at.replace(' ', 'T') + '+08:00' : null }
  if (selectedExecutorIds.value.length > 1 || editing.value?.has_allocations) payload.allocations = allocationDrafts.value.map(item => ({ executor_id:item.executor_id, content:item.content, due_at:item.due_at ? item.due_at.replace(' ', 'T') + '+08:00' : null }))
  try {
    if (requirementContext.value) {
      const { name, ...sourceFields } = payload
      await saveRequirementTask(requirementContext.value.room_id, { ...sourceFields, source_revision: requirementContext.value.source_revision, task_revision: editing.value?.revision || null, suffix: sourceSuffix.value })
      await router.replace({ path: route.path, query: { ...route.query, technicalRoomId: undefined }, hash: route.hash })
    }
    else if (editing.value) await api.updateDevelopmentTask(editing.value.id, { ...payload, revision: editing.value.revision })
    else await api.createDevelopmentTask({ ...payload, parent_id: parent_id || null })
    editorVisible.value = false; detail.value = null; ElMessage.success('任务已保存'); emit('saved'); if (!props.dialogOnly) await load()
  } catch (e) { saveError.value = message(e, '保存任务失败') } finally { saving.value = false }
}
async function openRequirement(roomId) {
  if (!roomId) return
  try {
    const value = await getRequirementTask(String(roomId))
    openEditor(value.task || null)
    requirementContext.value = value
    sourceSuffix.value = value.task?.source?.suffix || ''
    form.name = value.task?.name || value.source_name
    form.content = value.requirements
    if (!value.task) { form.arranger_id = value.arranger_id; form.executor_id = value.default_executor_id; selectedExecutorIds.value = [value.default_executor_id]; confirmedExecutorIds.value = [...selectedExecutorIds.value] }
  } catch (e) { ElMessage.error(message(e, '技术需求带入失败')) }
}
watch(() => route?.query?.technicalRoomId, value => { if (!props.dialogOnly) openRequirement(value) }, { immediate: true })

const detail = ref(null), detailLoading = ref(false), detailError = ref('')
let detailSequence = 0
async function loadDetail(id) {
  const current = ++detailSequence; detail.value = null; detailLoading.value = true; detailError.value = ''
  try { const result = await api.getDevelopmentTask(id); if (current === detailSequence) detail.value = result }
  catch (e) { if (current === detailSequence) detailError.value = message(e, '详情加载失败') }
  finally { if (current === detailSequence) detailLoading.value = false }
}
const detailFields = computed(() => { const d = detail.value || {}; return [{ label: '任务编号', value: d.task_no }, { label: '任务名称', value: d.name }, { label: '上级任务', value: rows.value.find(row => row.id === d.parent_id)?.name || '一级任务' }, { label: '具体任务', value: d.content }, { label: '安排人', value: d.arranger_name }, { label: '执行人', value: d.executor_name }, { label: '预定完成时间', value: formatTime(d.due_at) }, { label: '完成日期', value: d.completed_on }, { label: '是否按时完成', value: d.on_time == null ? '待完成' : d.on_time ? '是' : '否' }, { label: '具体进度', value: `${d.progress}%` }, { label: '进度修改时间', value: formatTime(d.progress_updated_at) }, { label: '反馈后调整', value: d.adjustment }, { label: '备注', value: d.notes }, { label: '创建时间', value: formatTime(d.created_at) }, { label: '更新时间', value: formatTime(d.updated_at) }] })

const activityVisible = ref(false), activity = ref(null), activityMode = ref('progress'), activityLoading = ref(false), activityError = ref(''), progressForm = ref(null), feedbackForm = ref(null)
const progress = reactive({ percentage: 1, content: '', reason: '' }), feedback = reactive({ content: '' })
const progressRules = computed(() => ({ percentage: [{ required: true, type: 'number', min: 1, max: 100, message: '请输入1—100的整数', trigger: 'change' }], reason: [{ validator: (_, value, callback) => callback(progress.percentage < (activity.value?.progress || 0) && !value.trim() ? new Error('进度回退必须填写修改原因') : undefined), trigger: 'blur' }] }))
const feedbackRules = { content: [{ required: true, whitespace: true, message: '请填写反馈意见', trigger: 'blur' }] }
let activitySequence = 0
async function openActivity(row, mode) {
  const current = ++activitySequence; activityMode.value = mode; activity.value = null; activityVisible.value = true; activityLoading.value = true; activityError.value = ''; feedback.content = ''; progress.content = ''; progress.reason = ''
  try { const result = await api.getDevelopmentTask(row.id); if (current === activitySequence) { activity.value = result; progress.percentage = result.progress || 1 } }
  catch (e) { if (current === activitySequence) activityError.value = message(e, '记录加载失败') }
  finally { if (current === activitySequence) activityLoading.value = false }
}
function closeActivity(done) { if (!saving.value) done() }
async function saveActivity() {
  const target = activityMode.value === 'progress' ? progressForm : feedbackForm
  if (saving.value || !activity.value || !await target.value.validate().catch(() => false)) return
  saving.value = true; activityError.value = ''
  try {
    const result = activityMode.value === 'progress' ? await api.saveDevelopmentProgress(activity.value.id, { ...progress, revision: activity.value.revision }) : await api.addDevelopmentFeedback(activity.value.id, { content: feedback.content })
    activity.value = result; progress.percentage = result.progress || 1; progress.content = ''; progress.reason = ''; feedback.content = ''; detail.value = null; ElMessage.success('记录已保存'); await load()
  } catch (e) { activityError.value = message(e, '记录保存失败') } finally { saving.value = false }
}

const draggingId = ref(null), dropTarget = ref(null), moving = ref(false), moveVisible = ref(false), moveRow = ref(null), moveParent = ref(null)
function startDrag(event, row) { if (moving.value || deleteMode.value) { event.preventDefault(); return } draggingId.value = row.id; event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', row.id) }
function endDrag() { draggingId.value = null; dropTarget.value = null }
async function dropTask(parentId) { const row = rows.value.find(item => item.id === draggingId.value); endDrag(); if (row) await performMove(row, parentId) }
const moveOptions = computed(() => rows.value.filter(row => canMoveTask(rows.value, moveRow.value?.id, row.id)))
function openMove(id) { moveRow.value = rows.value.find(row => row.id === id); moveParent.value = moveRow.value.parent_id; moveVisible.value = true }
function closeMove(done) { if (!moving.value) done() }
async function performMove(row, parentId) {
  parentId = parentId || null
  if (!row || moving.value || row.parent_id === parentId) { moveVisible.value = false; return }
  if (!canMoveTask(rows.value, row.id, parentId)) { ElMessage.warning('不能移入自身或子任务，且任务最多三级'); return }
  moving.value = true
  try { await api.moveDevelopmentTask(row.id, { parent_id: parentId, revision: row.revision }); moveVisible.value = false; detail.value = null; await load(); ElMessage.success('任务层级已调整') }
  catch (e) { ElMessage.error(message(e, '层级调整失败')) } finally { moving.value = false }
}
</script>

<style scoped>
.page-title{font-size:18px;font-weight:600}.page-header,.actions,.filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.page-header{justify-content:space-between}.filters{margin-bottom:12px}.filters>.el-input{width:450px;max-width:100%}.notice{margin-bottom:12px}.tree-help{padding:10px;margin-bottom:12px;border:1px dashed var(--el-border-color);color:var(--el-text-color-secondary);font-size:13px}.tree-help.is-dragging,.drop-target{background:var(--el-color-primary-light-9);outline:1px dashed var(--el-color-primary)}.task-name{display:inline-flex;align-items:center;gap:6px;min-width:120px;max-width:100%;overflow-wrap:anywhere}.drag-handle{border:0;background:transparent;color:var(--el-text-color-secondary);cursor:grab;font-size:20px;padding:0 4px}.drag-handle:active{cursor:grabbing}.progress-button{display:block;width:100%;border:0;background:transparent;cursor:pointer;text-align:left;padding:4px 0}.progress-button small{display:block;color:var(--el-text-color-secondary);margin-top:5px}.count{font-size:13px;color:var(--el-text-color-secondary);margin-top:12px}.task-detail{max-height:560px;overflow-y:auto;white-space:pre-wrap;overflow-wrap:anywhere}.task-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}.full{grid-column:1/-1}.task-form :deep(.el-select),.task-form :deep(.el-date-editor){width:100%}.task-form small{color:var(--el-text-color-secondary)}.history-record{border:1px solid var(--el-border-color);border-radius:6px;padding:12px;margin:10px 0}.history-record>div{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.history-record span{color:var(--el-text-color-secondary);font-size:12px}.history-record p,.activity-name{white-space:pre-wrap;overflow-wrap:anywhere}.move-entry{margin-top:12px}@media(max-width:680px){.task-form{grid-template-columns:1fr}}
</style>

<style>
.technical-task-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.technical-task-dialog>.el-dialog__header,.technical-task-dialog>.el-dialog__footer{flex-shrink:0}.technical-task-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.technical-task-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
</style>
