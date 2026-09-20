<template>
  <div class="arrangement-overview-page">
    <el-card class="page-header-card" shadow="never">
      <div class="page-heading">
        <div>
          <h2>标注项目安排</h2>
          <p>按日期集中查看项目安排和人员任务分布，并可直接调整项目任务。</p>
        </div>
        <el-button :loading="overviewLoading || workloadLoading" @click="refreshAll">刷新</el-button>
      </div>

      <div class="primary-filters">
        <div class="date-filter">
          <el-button-group>
            <el-button :type="quickDateOffset === -1 ? 'primary' : 'default'" @click="setQuickDate(-1)">昨日</el-button>
            <el-button :type="quickDateOffset === 0 ? 'primary' : 'default'" @click="setQuickDate(0)">今日</el-button>
            <el-button :type="quickDateOffset === 1 ? 'primary' : 'default'" @click="setQuickDate(1)">明日</el-button>
          </el-button-group>
          <el-date-picker
            v-model="filters.executionDate"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            :clearable="false"
            aria-label="安排日期"
            @change="runSearch"
          />
        </div>
        <el-select v-model="filters.arrangementStatus" aria-label="安排状态" @change="changeArrangementStatus">
          <el-option label="全部安排状态" value="all" />
          <el-option label="已安排" value="arranged" />
          <el-option label="未安排" value="unarranged" />
        </el-select>
        <el-select v-model="filters.projectStatus" clearable aria-label="项目进度" placeholder="全部项目进度" @change="runSearch">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索订单号、项目名称或客户名称"
          @input="onKeywordInput"
          @keyup.enter="runSearch"
          @clear="runSearch"
        />
        <el-button type="primary" @click="runSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <AdvancedFilterPopover
          v-model:visible="advancedVisible"
          :count="advancedCount"
          @clear="clearAdvancedFilters"
          @reset="clearAdvancedFilters"
        >
          <div class="advanced-grid">
            <label>
              <span>客户名称</span>
              <el-select v-model="filters.clientId" clearable filterable placeholder="全部客户" @change="runSearch">
                <el-option v-for="item in clientOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </label>
            <label>
              <span>项目类型</span>
              <el-select v-model="filters.projectType" clearable placeholder="全部项目类型" @change="runSearch">
                <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </label>
            <label>
              <span>项目经理</span>
              <el-select v-model="filters.projectManagerId" clearable filterable placeholder="全部项目经理" @change="runSearch">
                <el-option v-for="item in projectManagerOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </label>
            <label>
              <span>客户经理</span>
              <el-select v-model="filters.clientManagerId" clearable filterable placeholder="全部客户经理" @change="runSearch">
                <el-option v-for="item in userOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </label>
            <label>
              <span>任务类型</span>
              <el-select
                v-model="filters.taskTypeId"
                clearable
                filterable
                placeholder="全部任务类型"
                :disabled="filters.arrangementStatus === 'unarranged'"
                @change="runSearch"
              >
                <el-option v-for="item in taskTypes" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </label>
            <label>
              <span>执行人</span>
              <el-select
                v-model="filters.assigneeId"
                clearable
                filterable
                placeholder="全部执行人"
                :disabled="filters.arrangementStatus === 'unarranged'"
                @change="runSearch"
              >
                <el-option v-for="item in assignees" :key="item.id" :label="item.displayName" :value="item.id" />
              </el-select>
            </label>
          </div>
        </AdvancedFilterPopover>
      </div>
    </el-card>

    <section class="summary-grid" aria-label="安排统计">
      <button type="button" class="summary-card" @click="selectSummaryStatus('all')">
        <span>项目总数</span><strong>{{ summary.projectTotal }}</strong>
      </button>
      <button type="button" class="summary-card is-success" @click="selectSummaryStatus('arranged')">
        <span>已安排项目</span><strong>{{ summary.arrangedProjectCount }}</strong>
      </button>
      <button type="button" class="summary-card is-warning" @click="selectSummaryStatus('unarranged')">
        <span>未安排项目</span><strong>{{ summary.unarrangedProjectCount }}</strong>
      </button>
      <div class="summary-card is-info"><span>任务总数</span><strong>{{ summary.taskCount }}</strong></div>
      <div class="summary-card is-primary"><span>执行人数</span><strong>{{ summary.assigneeCount }}</strong></div>
    </section>

    <el-card class="overview-content" shadow="never">
      <el-tabs v-model="activeView">
        <el-tab-pane label="项目视图" name="projects">
          <div class="table-toolbar">
            <span>{{ selectedDateLabel }} · 共 {{ projectPagination.total }} 个项目</span>
            <div class="table-toolbar-actions">
              <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
              <el-select v-model="filters.sort" class="sort-select" @change="loadOverview">
                <el-option label="订单号倒序" value="order_no_desc" />
                <el-option label="订单号正序" value="order_no_asc" />
                <el-option label="项目名称正序" value="project_name_asc" />
                <el-option label="任务数量从多到少" value="task_count_desc" />
              </el-select>
            </div>
          </div>
          <el-table v-loading="overviewLoading" :data="projects" row-key="id" border>
            <el-table-column type="expand" width="48">
              <template #default="{ row }">
                <div class="expanded-tasks">
                  <el-table v-if="row.tasks.length" :data="row.tasks" border size="small">
                    <el-table-column prop="taskTypeName" label="任务类型" width="150" />
                    <el-table-column prop="assigneeName" label="执行人" width="140" />
                    <el-table-column prop="taskContent" label="任务内容" min-width="260" show-overflow-tooltip />
                  </el-table>
                  <el-empty v-else description="该日期暂无项目安排" :image-size="56" />
                </div>
              </template>
            </el-table-column>
            <el-table-column v-for="column in visibleTableColumns" :key="column.key" :label="column.label" :prop="column.key" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="!['orderNo','projectStatus','arrangementStatus'].includes(column.key)">
              <template #default="{ row }">
                <AnnotationProjectDetailPopover v-if="column.key === 'orderNo'" :project-id="row.id" :summary="row" :editable="canWrite">
                  <template #reference><el-button type="primary" link class="overview-order-link" @click.stop>{{ row.orderNo }}</el-button></template>
                </AnnotationProjectDetailPopover>
                <el-button v-else-if="column.key === 'projectStatus'" type="primary" link @click="openProjectProgress(row)">
                  <el-tag :type="statusType(row.projectStatus)" effect="plain">{{ statusLabel(row.projectStatus) }}</el-tag>
                </el-button>
                <el-tooltip v-else-if="column.key === 'taskDescription'" :content="textValue(row.taskDescription)" placement="top" :disabled="!row.taskDescription">
                  <span class="ellipsis-cell">{{ textValue(row.taskDescription) }}</span>
                </el-tooltip>
                <span v-else-if="column.key === 'projectTypes'">{{ projectTypesText(row.projectTypes) }}</span>
                <el-tag v-else-if="column.key === 'priority'" :type="priorityType(row.priority)" size="small">{{ priorityLabel(row.priority) }}</el-tag>
                <el-tag v-else-if="column.key === 'arrangementStatus'" :type="row.arrangementStatus === 'arranged' ? 'success' : 'warning'">
                  {{ row.arrangementStatus === 'arranged' ? '已安排' : '未安排' }}
                </el-tag>
                <span v-else-if="column.key === 'assigneeNames'">{{ row.assigneeNames?.join('、') || '-' }}</span>
                <span v-else-if="column.customField">{{ customFieldText(row.customValues?.[column.customField.id]) }}</span>
                <span v-else>{{ textValue(row[column.key]) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" :width="canManageArrangementPool ? 160 : 92" fixed="right" align="center">
              <template #default="{ row }">
                <el-button v-if="canWrite" type="primary" link @click="openArrangement(row)">
                  {{ row.arrangementStatus === 'arranged' ? '调整安排' : '立即安排' }}
                </el-button>
                <el-button v-if="canManageArrangementPool && row.arrangementScopeState === 'included'" type="danger" link :loading="membershipSavingIds.has(row.id)" @click="removeFromArrangementPool(row)">移出</el-button>
                <span v-if="!canWrite && !(canManageArrangementPool && row.arrangementScopeState === 'included')">-</span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="projectPagination.page"
            v-model:page-size="projectPagination.limit"
            :total="projectPagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadOverview"
            @size-change="projectPageSizeChanged"
          />
        </el-tab-pane>

        <el-tab-pane label="人员视图" name="people">
          <div class="workload-toolbar">
            <el-input
              v-model="workloadFilters.keyword"
              clearable
              placeholder="搜索姓名或部门"
              @input="onWorkloadKeywordInput"
              @keyup.enter="loadWorkloads(true)"
              @clear="loadWorkloads(true)"
            />
            <el-select v-model="workloadFilters.loadState" @change="loadWorkloads(true)">
              <el-option label="全部人员" value="all" />
              <el-option label="有安排" value="assigned" />
              <el-option label="无安排" value="unassigned" />
            </el-select>
            <span>{{ selectedDateLabel }} · 共 {{ workloadPagination.total }} 人</span>
          </div>
          <el-table v-loading="workloadLoading" :data="workloads" row-key="assigneeId" border>
            <el-table-column type="expand" width="48">
              <template #default="{ row }">
                <div class="expanded-tasks">
                  <el-table v-if="row.tasks.length" :data="row.tasks" border size="small">
                    <el-table-column prop="orderNo" label="订单号" width="145" />
                    <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
                    <el-table-column prop="taskTypeName" label="任务类型" width="145" />
                    <el-table-column prop="taskContent" label="任务内容" min-width="240" show-overflow-tooltip />
                    <el-table-column v-if="canWrite" label="操作" width="90" align="center">
                      <template #default="scope">
                        <el-button type="primary" link @click="openArrangementFromTask(scope.row)">调整</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                  <el-empty v-else description="该日期暂无任务" :image-size="56" />
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="assigneeName" label="姓名" min-width="135" />
            <el-table-column prop="department" label="部门" min-width="120">
              <template #default="{ row }">{{ row.department || '-' }}</template>
            </el-table-column>
            <el-table-column label="人员分组" width="120">
              <template #default="{ row }">{{ priorityGroupLabel(row.priorityGroup) }}</template>
            </el-table-column>
            <el-table-column prop="taskCount" label="任务数" width="90" align="center" sortable />
            <el-table-column prop="projectCount" label="项目数" width="90" align="center" sortable />
            <el-table-column label="涉及项目" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ row.projectNames.join('、') || '-' }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="workloadPagination.page"
            v-model:page-size="workloadPagination.limit"
            :total="workloadPagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadWorkloads"
            @size-change="workloadPageSizeChanged"
          />
        </el-tab-pane>

        <el-tab-pane label="今日安排" name="today" lazy>
          <AnnotationDailyArrangement :can-edit="canWrite" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <AnnotationProjectArrangementQuickDialog
      v-model="arrangementVisible"
      :initial-project="arrangementProject"
      :default-execution-date="filters.executionDate"
      :can-write="canWrite"
      :allow-new-tasks="arrangementProject?.arrangementScopeState !== 'history_only'"
      @saved="arrangementSaved"
      @project-change-rejected="arrangementProject = $event"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as annotationOpsApi from '@/api/annotationOps'
import * as clientApi from '@/api/clients'
import * as userApi from '@/api/users'
import { getProjectRoleCandidatesAPI } from '@/api/workflow'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import AnnotationProjectArrangementQuickDialog from '@/components/annotation/AnnotationProjectArrangementQuickDialog.vue'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
import AnnotationDailyArrangement from '@/components/annotation/AnnotationDailyArrangement.vue'
import { useAnnotationCustomFields } from '@/composables/useAnnotationCustomFields'
import { useTableColumns } from '@/composables/useTableColumns'
import { getProjectStatusLabel, getProjectStatusOptions, getProjectStatusType } from '@/utils/projectStatus'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { hasPermission, isSuperAdmin } from '@/utils/permission'

const BUSINESS_TIME_ZONE = 'Asia/Hong_Kong'
const canWrite = hasPermission('projects:write')
const canManageArrangementPool = isSuperAdmin()
const router = useRouter()
const activeView = ref('projects')
const advancedVisible = ref(false)
const overviewLoading = ref(false)
const workloadLoading = ref(false)
const projects = ref([])
const workloads = ref([])
const taskTypes = ref([])
const assignees = ref([])
const clients = ref([])
const users = ref([])
const projectManagers = ref([])
const arrangementVisible = ref(false)
const arrangementProject = ref(null)
const membershipSavingIds = ref(new Set())
const summary = reactive({ projectTotal:0, arrangedProjectCount:0, unarrangedProjectCount:0, taskCount:0, assigneeCount:0 })
const projectPagination = reactive({ page:1, limit:20, total:0 })
const workloadPagination = reactive({ page:1, limit:20, total:0 })
const workloadFilters = reactive({ keyword:'', loadState:'all' })
let overviewController = null
let overviewRequestId = 0
let workloadController = null
let workloadRequestId = 0
let keywordTimer = null
let workloadKeywordTimer = null

const businessDate = (offset = 0, now = new Date()) => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone:BUSINESS_TIME_ZONE, year:'numeric', month:'2-digit', day:'2-digit',
  }).formatToParts(now).filter((item) => item.type !== 'literal').map((item) => [item.type,item.value]))
  const date = new Date(Date.UTC(Number(parts.year), Number(parts.month)-1, Number(parts.day)+offset))
  return date.toISOString().slice(0,10)
}

const filters = reactive({
  executionDate:businessDate(), arrangementStatus:'all', projectStatus:'', keyword:'',
  clientId:'', projectType:'', projectManagerId:'', clientManagerId:'', taskTypeId:'', assigneeId:'',
  sort:'order_no_desc',
})

const statusOptions = getProjectStatusOptions('annotation')
const projectTypeOptions = [
  ['audio_collection','音频采集'],['audio_annotation','音频标注'],['audio_evaluation','音频评测'],
  ['text_evaluation','文本评测'],['text_annotation','文本标注'],['quality_inspection','质检'],
  ['listening_test','测听'],['slot_deduction','扣槽'],['generalization','泛化'],['translation','翻译'],['ai_evaluation','AI评测'],
].map(([value,label]) => ({ value,label }))
const projectTypeMap = Object.fromEntries(projectTypeOptions.map(item => [item.value,item.label]))
const arrangementStaticColumns = [
  {key:'orderNo',label:'订单号',width:145},
  {key:'clientShortName',label:'客户简称',width:130},
  {key:'projectName',label:'项目名称',minWidth:190},
  {key:'projectTypes',label:'项目类型',minWidth:115},
  {key:'taskDescription',label:'具体任务',minWidth:210},
  {key:'projectStatus',label:'项目进度',width:125},
  {key:'priority',label:'优先次序',width:96},
  {key:'clientManagerName',label:'客户经理',width:125},
  {key:'projectManagerName',label:'项目经理',width:125},
  {key:'languageItemsDisplay',label:'语言方向',minWidth:140},
  {key:'potentialDemand',label:'（潜在）需求量',minWidth:135},
  {key:'arrangementStatus',label:'安排状态',width:100},
  {key:'taskCount',label:'任务数',width:80},
  {key:'assigneeNames',label:'执行人',minWidth:150},
]
const { fields:projectCustomFields, load:loadProjectCustomFields } = useAnnotationCustomFields('project')
const customTableColumns = computed(() => projectCustomFields.value.filter(field => field.isActive !== false).map(field => ({
  key:`custom:${field.id}`, label:field.fieldLabel,
  minWidth:['text','url'].includes(field.dataType) ? 160 : 110,
  customField:field,
})))
const tableColumns = computed(() => [...arrangementStaticColumns,...customTableColumns.value])
const defaultColumns = arrangementStaticColumns.map(item => item.key)
const { selectedKeys:visibleColumnKeys, isVisible, reset:resetColumns } = useTableColumns(
  'annotation-arrangements-v1', tableColumns, defaultColumns,
)
const visibleTableColumns = computed(() => tableColumns.value.filter(item => isVisible(item.key)))
const quickDateOffset = computed(() => [-1,0,1].find((offset) => businessDate(offset) === filters.executionDate) ?? null)
const selectedDateLabel = computed(() => ({'-1':'昨日安排','0':'今日安排','1':'明日安排'}[String(quickDateOffset.value)] || `${filters.executionDate} 安排`))
const clientOptions = computed(() => clients.value.map((item) => ({
  value:item.id, label:item.client_short_name || item.client_name || item.clientShortName || item.clientName || '-',
})))
const userOptions = computed(() => users.value.filter((item) => item.is_active ?? item.isActive ?? true).map((item) => ({
  value:item.id, label:item.full_name || item.fullName || item.username,
})))
const projectManagerOptions = computed(() => projectManagers.value.map((item) => ({
  value:item.id, label:item.display_name || item.displayName || item.full_name || item.fullName || item.username,
})))
const advancedCount = computed(() => [
  filters.clientId, filters.projectType, filters.projectManagerId,
  filters.clientManagerId, filters.taskTypeId, filters.assigneeId,
].filter(Boolean).length)

const statusLabel = (value) => getProjectStatusLabel('annotation', value)
const statusType = (value) => getProjectStatusType('annotation', value)
const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
const projectTypesText = (values) => (values || []).map(value => projectTypeMap[value] || value).join('、') || '-'
const priorityLabel = (value) => ({low:'低',medium:'中',high:'高'}[value] || value || '-')
const priorityType = (value) => ({low:'info',medium:'warning',high:'danger'}[value] || 'info')
const customFieldText = (value) => Array.isArray(value) ? value.join('、') : textValue(value)
const priorityGroupLabel = (value) => ({project_manager:'项目经理',hr:'HR',other:'其他员工'}[value] || value || '-')
const compactParams = (values) => Object.fromEntries(Object.entries(values).filter(([,value]) => value !== '' && value !== null && value !== undefined))
const commonProjectParams = () => compactParams({
  executionDate:filters.executionDate,
  keyword:filters.keyword.trim() || undefined,
  projectStatus:filters.projectStatus || undefined,
  clientId:filters.clientId || undefined,
  projectType:filters.projectType || undefined,
  projectManagerId:filters.projectManagerId || undefined,
  clientManagerId:filters.clientManagerId || undefined,
  taskTypeId:filters.taskTypeId || undefined,
})

async function loadOverview(resetPage = false) {
  if (resetPage === true) projectPagination.page = 1
  overviewController?.abort()
  overviewController = new AbortController()
  const requestId = ++overviewRequestId
  overviewLoading.value = true
  try {
    const response = await annotationOpsApi.getProjectArrangementOverview(compactParams({
      ...commonProjectParams(), arrangementStatus:filters.arrangementStatus,
      assigneeId:filters.assigneeId || undefined,
      skip:(projectPagination.page-1)*projectPagination.limit, limit:projectPagination.limit, sort:filters.sort,
    }), { signal:overviewController.signal })
    if (requestId !== overviewRequestId) return
    projects.value = response.items || []
    projectPagination.total = response.total || 0
    Object.assign(summary, response.summary || {})
    taskTypes.value = response.taskTypes || []
    assignees.value = response.assignees || []
  } catch (error) {
    if (requestId !== overviewRequestId || error?.code === 'ERR_CANCELED') return
    ElMessage.error(getLocalizedErrorMessage(error, '项目安排概览加载失败'))
  } finally {
    if (requestId === overviewRequestId) overviewLoading.value = false
  }
}

async function loadWorkloads(resetPage = false) {
  if (resetPage === true) workloadPagination.page = 1
  workloadController?.abort()
  workloadController = new AbortController()
  const requestId = ++workloadRequestId
  workloadLoading.value = true
  try {
    const response = await annotationOpsApi.getProjectArrangementWorkloads(compactParams({
      ...commonProjectParams(), projectKeyword:filters.keyword.trim() || undefined, keyword:workloadFilters.keyword.trim() || undefined,
      assigneeId:filters.assigneeId || undefined, loadState:workloadFilters.loadState,
      skip:(workloadPagination.page-1)*workloadPagination.limit, limit:workloadPagination.limit,
    }), { signal:workloadController.signal })
    if (requestId !== workloadRequestId) return
    workloads.value = response.items || []
    workloadPagination.total = response.total || 0
  } catch (error) {
    if (requestId !== workloadRequestId || error?.code === 'ERR_CANCELED') return
    ElMessage.error(getLocalizedErrorMessage(error, '人员安排负荷加载失败'))
  } finally {
    if (requestId === workloadRequestId) workloadLoading.value = false
  }
}

const refreshAll = () => Promise.all([loadOverview(), loadWorkloads()])
const runSearch = () => {
  projectPagination.page = 1
  workloadPagination.page = 1
  return refreshAll()
}
const onKeywordInput = () => {
  clearTimeout(keywordTimer)
  if (!filters.keyword) return runSearch()
  keywordTimer = setTimeout(runSearch, 400)
}
const onWorkloadKeywordInput = () => {
  clearTimeout(workloadKeywordTimer)
  if (!workloadFilters.keyword) return loadWorkloads(true)
  workloadKeywordTimer = setTimeout(() => loadWorkloads(true), 400)
}
const setQuickDate = (offset) => { filters.executionDate = businessDate(offset); runSearch() }
const changeArrangementStatus = () => {
  if (filters.arrangementStatus === 'unarranged') {
    filters.taskTypeId = ''
    filters.assigneeId = ''
  }
  runSearch()
}
const selectSummaryStatus = (status) => { filters.arrangementStatus = status; changeArrangementStatus() }
const clearAdvancedFilters = () => {
  Object.assign(filters, {clientId:'',projectType:'',projectManagerId:'',clientManagerId:'',taskTypeId:'',assigneeId:''})
  runSearch()
}
const resetFilters = () => {
  Object.assign(filters, {
    executionDate:businessDate(), arrangementStatus:'all', projectStatus:'', keyword:'', clientId:'',
    projectType:'', projectManagerId:'', clientManagerId:'', taskTypeId:'', assigneeId:'', sort:'order_no_desc',
  })
  Object.assign(workloadFilters, {keyword:'',loadState:'all'})
  runSearch()
}
const projectPageSizeChanged = () => { projectPagination.page = 1; loadOverview() }
const workloadPageSizeChanged = () => { workloadPagination.page = 1; loadWorkloads() }
const openArrangement = (row) => { arrangementProject.value = row; arrangementVisible.value = true }
const openProjectProgress = (row) => router.push({
  name:'AnnotationProjectDetails', query:{ section:'projects', projectId:row.id, openProgress:'1' },
})
const removeFromArrangementPool = async (row) => {
  try {
    await ElMessageBox.confirm('移出安排池不会删除历史安排任务，是否继续？','移出项目安排',{type:'warning',confirmButtonText:'移出安排'})
  } catch { return }
  membershipSavingIds.value = new Set([...membershipSavingIds.value,row.id])
  try {
    await annotationOpsApi.setProjectArrangementMembership(row.id, {
      included:false, expectedUpdatedAt:row.arrangementMembershipUpdatedAt || null,
    })
    ElMessage.success('已移出项目安排')
    await refreshAll()
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error,'移出项目安排失败')) }
  finally { const next=new Set(membershipSavingIds.value);next.delete(row.id);membershipSavingIds.value=next }
}
const openArrangementFromTask = (task) => openArrangement({id:task.projectId,orderNo:task.orderNo,projectName:task.projectName})
const arrangementSaved = async () => { await refreshAll() }

async function loadReferenceData() {
  const results = await Promise.allSettled([
    clientApi.getClients({skip:0,limit:500,frequent_first:true}),
    userApi.getUsers({skip:0,limit:500}),
    getProjectRoleCandidatesAPI('project_manager'),
  ])
  clients.value = results[0].status === 'fulfilled' && Array.isArray(results[0].value) ? results[0].value : []
  users.value = results[1].status === 'fulfilled' && Array.isArray(results[1].value) ? results[1].value : []
  projectManagers.value = results[2].status === 'fulfilled' && Array.isArray(results[2].value) ? results[2].value : []
}

onMounted(() => Promise.all([loadReferenceData(), loadProjectCustomFields(), refreshAll()]))
onBeforeUnmount(() => {
  clearTimeout(keywordTimer)
  clearTimeout(workloadKeywordTimer)
  overviewController?.abort()
  workloadController?.abort()
})
</script>

<style scoped>
.arrangement-overview-page{display:grid;gap:14px}.page-header-card :deep(.el-card__body){display:grid;gap:16px}.page-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.page-heading h2{margin:0;font-size:22px}.page-heading p{margin:6px 0 0;color:var(--el-text-color-secondary)}.primary-filters{display:grid;grid-template-columns:minmax(310px,auto) 150px 190px minmax(240px,1fr) auto auto auto;align-items:center;gap:10px}.date-filter{display:flex;align-items:center;gap:8px}.date-filter .el-date-editor{width:138px}.advanced-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.advanced-grid label{display:grid;gap:5px;color:var(--el-text-color-secondary);font-size:12px}.summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.summary-card{display:flex;align-items:center;justify-content:space-between;min-height:82px;padding:16px 18px;border:1px solid var(--el-border-color-light);border-radius:10px;background:var(--el-bg-color);color:var(--el-text-color-regular);font:inherit;text-align:left;box-shadow:var(--el-box-shadow-lighter)}button.summary-card{cursor:pointer}.summary-card:hover{border-color:var(--el-color-primary-light-5)}.summary-card strong{font-size:28px;color:var(--el-text-color-primary)}.summary-card.is-success strong{color:var(--el-color-success)}.summary-card.is-warning strong{color:var(--el-color-warning)}.summary-card.is-info strong{color:var(--el-color-info)}.summary-card.is-primary strong{color:var(--el-color-primary)}.overview-content :deep(.el-card__body){padding-top:4px}.table-toolbar,.workload-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;color:var(--el-text-color-secondary);font-size:13px}.sort-select{width:190px}.workload-toolbar{justify-content:flex-start}.workload-toolbar .el-input{width:280px}.workload-toolbar .el-select{width:140px}.workload-toolbar span{margin-left:auto}.expanded-tasks{padding:10px 52px;background:var(--el-fill-color-lighter)}.el-pagination{justify-content:flex-end;margin-top:14px}
.table-toolbar-actions{display:flex;align-items:center;gap:8px}.overview-order-link{display:block;width:100%;height:auto;padding:0;overflow:hidden;text-align:left;text-overflow:ellipsis;white-space:nowrap}.ellipsis-cell{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:1200px){.primary-filters{grid-template-columns:repeat(3,minmax(0,1fr))}.primary-filters>.el-input{grid-column:span 2}.summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){.page-heading{align-items:stretch;flex-direction:column}.primary-filters{grid-template-columns:minmax(0,1fr)}.primary-filters>.el-input{grid-column:span 1}.date-filter{align-items:stretch;flex-direction:column}.date-filter .el-button-group{display:flex}.date-filter .el-button{flex:1}.date-filter .el-date-editor{width:100%}.advanced-grid{grid-template-columns:minmax(0,1fr)}.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.summary-card{min-height:70px;padding:12px}.summary-card strong{font-size:23px}.table-toolbar,.workload-toolbar{align-items:stretch;flex-direction:column}.sort-select,.workload-toolbar .el-input,.workload-toolbar .el-select{width:100%}.workload-toolbar span{margin-left:0}.expanded-tasks{padding:8px}.el-pagination{justify-content:flex-start;overflow-x:auto}}
</style>
