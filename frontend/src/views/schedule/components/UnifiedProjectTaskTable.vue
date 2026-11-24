<template>
  <section class="unified-project-tasks">
    <div class="unified-task-toolbar">
      <el-input v-model="keyword" clearable placeholder="搜索订单号、项目名称、客户或具体任务"
        aria-label="搜索项目任务" @keyup.enter="query" />
      <el-button @click="query">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>
    <div v-if="availableTypes.length" class="project-status-filters">
      <template v-for="type in availableTypes.filter(type => type.statuses.length)" :key="type.value">
        <label :for="'task-status-' + type.value">{{ type.label }}状态</label>
        <el-select :id="'task-status-' + type.value" v-model="statuses[type.value]" multiple collapse-tags
          collapse-tags-tooltip clearable filterable :aria-label="type.label + '状态'" placeholder="全部状态" @change="query">
          <el-option v-for="status in type.statuses" :key="status" :value="status"
            :label="getProjectStatusLabel(type.value, status)" />
        </el-select>
      </template>
    </div>
    <ArrangementDateFilter v-model="dateRange" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border row-key="row_key">
      <el-table-column type="index" label="序号" width="55" />
      <el-table-column label="项目类型" width="135">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.project_type" :definition="definitions.project_type" @change="query" @clear="query" /></template>
        <template #default="{ row }">{{ row.project_type_label }}</template>
      </el-table-column>
      <el-table-column label="订单号" width="165">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.order_no" :definition="definitions.order_no" @change="query" @clear="query" /></template>
        <template #default="{ row }">
          <AnnotationProjectDetailPopover v-if="row.annotation_summary" :project-id="row.project_id"
            :summary="row.annotation_summary" :editable="canWrite" @updated="refresh">
            <template #reference><el-button type="primary" link @click.stop>{{ row.order_no }}</el-button></template>
          </AnnotationProjectDetailPopover>
          <el-button v-else-if="row.project_id" type="primary" link @click="openProject(row)">{{ row.order_no }}</el-button>
          <span v-else>{{ row.order_no || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="项目名称" min-width="220" show-overflow-tooltip>
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.project_name" :definition="definitions.project_name" @change="query" @clear="query" /></template>
        <template #default="{ row }">
          <el-button v-if="row.project_type === 'annotation' && row.project_id" link type="primary"
            class="task-project-name" @click="progressProjectId = row.project_id">{{ row.project_name }}</el-button>
          <span v-else>{{ row.project_name || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="client_name" label="客户简称" min-width="130" show-overflow-tooltip>
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.client_name" :definition="definitions.client_name" @change="query" @clear="query" /></template>
      </el-table-column>
      <el-table-column label="客户要求" width="100">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.customer_requirements" :definition="definitions.customer_requirements" @change="query" @clear="query" /></template>
        <template #default="{ row }"><CustomerProjectRequirements :professional="row.customer_requirement_professional"
          :special="row.customer_requirement_special" /></template>
      </el-table-column>
      <el-table-column label="共同说明" min-width="180">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.common_instruction" :definition="definitions.common_instruction" @change="query" @clear="query" /></template>
        <template #default="{ row }">
          <el-popover v-if="row.common_instruction" trigger="click" placement="left" :width="560" title="项目共同说明"
            popper-class="task-common-instruction-popover">
            <div class="task-common-instruction-content">{{ row.common_instruction }}</div>
            <template #reference><el-button link type="primary" class="common-instruction-preview">{{ row.common_instruction }}</el-button></template>
          </el-popover><span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="具体任务" min-width="240" show-overflow-tooltip>
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.content" :definition="definitions.content" @change="query" @clear="query" /></template>
      </el-table-column>
      <el-table-column label="执行顺序" min-width="240">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.execution_sequence" :definition="definitions.execution_sequence" @change="query" @clear="query" /></template>
        <template #default="{ row }"><ExecutionSequence v-if="row.source === 'assigned'"
          :sequence="row.execution_sequence || []" :current-id="row.id" /><span v-else>-</span></template>
      </el-table-column>
      <el-table-column label="项目状态" width="150">
        <template #default="{ row }">
          <el-button v-if="row.project_type === 'annotation' && row.project_id" type="primary" link @click="progressProjectId = row.project_id">
            <el-tag :type="annotationStatusType(row.project_status)" size="small">
              {{ annotationStatusLabel(row.project_status) }}<el-icon><EditPen /></el-icon>
            </el-tag>
          </el-button><span v-else>{{ getProjectStatusLabel(row.project_type, row.project_status) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="安排状态" width="140">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.arrangement_status" :definition="definitions.arrangement_status" @change="query" @clear="query" /></template>
        <template #default="{ row }">{{ row.project_type === 'annotation' ? (row.arrangement_status === 'not_today' ? '今日暂不进行' : '今日进行中') : '-' }}</template>
      </el-table-column>
      <el-table-column prop="work_date" label="安排日期" width="130">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.work_date" :definition="definitions.work_date" @change="query" @clear="query" /></template>
        <template #default="{ row }">{{ row.work_date || '-' }}</template>
      </el-table-column>
      <el-table-column v-for="field in timeFields" :key="field.key" :label="field.label" width="155">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters[field.key]" :definition="definitions[field.key]" @change="query" @clear="query" /></template>
        <template #default="{ row }">
          <el-select v-if="row.source !== 'project' && row.status !== 'completed'" :disabled="saving"
            :model-value="row[field.key]" @change="$emit('save-task', row, { [field.key]: $event })">
            <el-option :value="0" label="未填写" />
            <el-option v-for="minutes in durationOptions" :key="minutes" :value="minutes" :label="durationLabel(minutes)" />
          </el-select><span v-else>{{ row.source === 'project' ? '-' : durationLabel(row[field.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="任务状态" width="145">
        <template #header><ConfiguredColumnHeaderFilter v-model="filters.task_status" :definition="definitions.task_status" @change="query" @clear="query" /></template>
        <template #default="{ row }">
          <el-select v-if="row.source !== 'project' && row.status !== 'completed'" :model-value="row.status" :disabled="saving"
            @change="$emit('status-change', row, $event)">
            <el-option v-for="(label, value) in taskLabels" :key="value" :label="label" :value="value" />
          </el-select><span v-else>{{ taskLabels[row.task_status] || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.source === 'personal' && row.status !== 'completed'" link type="primary"
            @click="$emit('edit-personal', row)">编辑任务</el-button>
          <el-button v-if="row.can_arrange_annotation || row.project_type === 'interpretation'" link type="primary"
            @click="openTodayArrangement(row)">今日安排</el-button>
          <el-button v-if="row.project_type === 'annotation' && row.project_id && canOpen" link type="primary"
            @click="activeProject = row.annotation_summary; arrangementVisible = true">项目安排</el-button>
          <el-button v-if="row.project_id" link type="primary" @click="openProject(row)">进入项目</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total, prev, pager, next" @current-change="load" />
    <AnnotationProjectArrangementDialog v-if="activeProject" v-model="arrangementVisible" :initial-project="activeProject"
      :default-execution-date="day" :can-write="canWrite" @saved="refresh" />
    <AnnotationProgressHost v-if="progressProjectId" :key="progressProjectId" embedded progress-only
      :progress-project-id="progressProjectId" @progress-closed="progressProjectId = ''; refresh()" />
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getUnifiedProjectTasks } from '@/api/tasks'
import { getProjectStatusLabel } from '@/utils/projectStatus'
import { annotationStatusLabel, annotationStatusType } from '@/utils/annotationStatus'
import { EditPen } from '@element-plus/icons-vue'
import { openAnnotationWorkStatus } from '@/utils/annotationWorkStatus'
import { hasPermission } from '@/utils/permission'
import { durationLabel, durationOptions, reportBusinessDate } from '@/utils/workReportForm'
import ArrangementDateFilter from '@/components/common/ArrangementDateFilter.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import CustomerProjectRequirements from '@/components/common/CustomerProjectRequirements.vue'
import ExecutionSequence from '@/components/common/ExecutionSequence.vue'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'

const props = defineProps({ day: String, saving: Boolean })
const emit = defineEmits(['open-project', 'save-task', 'status-change', 'edit-personal', 'types-change', 'loading-change'])
const AnnotationProjectArrangementDialog = defineAsyncComponent(() => import('@/components/annotation/AnnotationProjectArrangementDialog.vue'))
const AnnotationProgressHost = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const canWrite = hasPermission('projects:write')
const canOpen = canWrite || hasPermission('projects:read')
const keyword = ref('')
const dateRange = ref(null)
const statuses = reactive({})
const defaultFilters = () => ({
  project_type: [], task_status: [], arrangement_status: [],
  order_no: '', project_name: '', client_name: '', content: '', customer_requirements: '',
  common_instruction: '', work_date: '', estimated_minutes: '', actual_minutes: '',
  execution_sequence: '',
})
const filters = reactive(defaultFilters())
const availableTypes = ref([])
const rows = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
watch(loading, value => emit('loading-change', value), { flush: 'sync' })
const error = ref('')
const progressProjectId = ref('')
const activeProject = ref(null)
const arrangementVisible = ref(false)
const taskLabels = { pending: '待进行', in_progress: '进行中', completed: '已完成' }
const timeFields = [{ key: 'estimated_minutes', label: '预计需要时间' }, { key: 'actual_minutes', label: '实际花费时间' }]
const definitions = computed(() => ({
  project_type: { key: 'project_type', label: '项目类型', type: 'select', options: availableTypes.value },
  ...Object.fromEntries([
    ['order_no', '订单号'], ['project_name', '项目名称'], ['client_name', '客户简称'], ['content', '具体任务'],
    ['customer_requirements', '客户要求'], ['common_instruction', '共同说明'],
    ['execution_sequence', '执行顺序'],
    ['work_date', '安排日期'], ['estimated_minutes', '预计需要时间'], ['actual_minutes', '实际花费时间'],
  ].map(([key, label]) => [key, { key, label, type: 'text',
    placeholder: key.endsWith('_minutes') ? '输入分钟数' : key === 'work_date' ? '如 2026-11-24' : key === 'execution_sequence' ? '搜索执行人员或任务内容' : '输入关键词' }])),
  task_status: { key: 'task_status', label: '任务状态', type: 'select',
    options: Object.entries(taskLabels).map(([value, label]) => ({ value, label })) },
  arrangement_status: { key: 'arrangement_status', label: '安排状态', type: 'select',
    options: [{ value: 'in_progress', label: '今日进行中' }, { value: 'not_today', label: '今日暂不进行' }] },
}))
let controller, sequence = 0, timer

async function load() {
  clearTimeout(timer)
  controller?.abort()
  const current = ++sequence
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const result = await getUnifiedProjectTasks({
      day: props.day || reportBusinessDate(), keyword: keyword.value.trim(),
      filters: JSON.stringify(filters), statuses: JSON.stringify(statuses), page: page.value,
      date_from: dateRange.value?.[0], date_to: dateRange.value?.[1],
    }, { signal: controller.signal })
    if (current !== sequence) return
    rows.value = result.items
    total.value = result.total
    availableTypes.value = result.project_types
    emit('types-change', result.project_types)
    if (!rows.value.length && total.value && page.value > 1) {
      page.value = Math.ceil(total.value / 20)
      return load()
    }
  } catch (reason) {
    if (current === sequence && reason.code !== 'ERR_CANCELED') error.value = reason.detail || '读取项目任务失败'
  } finally {
    if (current === sequence) loading.value = false
  }
}
function query() { page.value = 1; return load() }
function refresh() { return load() }
function reset() {
  keyword.value = ''
  Object.assign(filters, defaultFilters())
  Object.keys(statuses).forEach(key => delete statuses[key])
  dateRange.value = null
  return query()
}
function openProject(row) { emit('open-project', { ...row, id: row.project_id }) }
function openTodayArrangement(row) {
  openAnnotationWorkStatus({ mode: 'arrangement', projectId: row.project_id,
    ...(row.project_type === 'interpretation' ? { projectType: 'interpretation' } : {}) })
}
watch(keyword, value => {
  clearTimeout(timer)
  sequence++
  controller?.abort()
  if (!value.trim()) query()
  else timer = setTimeout(query, 400)
})
watch(dateRange, query)
watch(() => props.day, () => { dateRange.value = null; query() })
const updates = ['annotation-work-status-updated', 'interpretation-work-arrangement-updated']
onMounted(() => { load(); updates.forEach(event => window.addEventListener(event, refresh)) })
onBeforeUnmount(() => {
  clearTimeout(timer)
  sequence++
  controller?.abort()
  updates.forEach(event => window.removeEventListener(event, refresh))
})
defineExpose({ refresh })
</script>

<style scoped>
.unified-task-toolbar, .project-status-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.unified-task-toolbar .el-input { width: min(420px, 100%); }
.unified-task-toolbar .el-button { margin-left: 0; }
.project-status-filters .el-select { width: 180px; }
.project-status-filters label { font-size: 13px; }
.common-instruction-preview, .task-project-name { display: block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: left; }
.el-pagination { margin-top: 12px; justify-content: flex-end; }
</style>
