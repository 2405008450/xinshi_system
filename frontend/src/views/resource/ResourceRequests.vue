<template>
  <div class="resource-request-page">
    <el-card>
      <template #header>
        <div class="header">
          <div>
            <h2>资源需求管理</h2>
            <p>统一跟踪标注、招聘、口译、笔译及其他资源请求</p>
          </div>
          <div class="header-actions">
            <TableColumnSettings
              v-model="selectedColumnKeys"
              :columns="tableColumns"
              :column-count="2"
              hint="序号、详情和操作列固定显示；订单号、客户编号等字段默认隐藏，可按需启用。"
              @reset="resetColumns"
            />
            <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
            <el-button v-if="canWrite && !deleteMode" type="primary" @click="openEditor()">新增资源需求</el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-input
          v-model="searchForm.keyword"
          clearable
          placeholder="搜索请求编号、项目、客户或需求详情"
          style="width: 330px"
          @input="onKeyword"
          @keyup.enter="search"
        />
        <el-select v-model="searchForm.requestStatus" clearable placeholder="请求状态" style="width: 140px" @change="search">
          <el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="advancedWidth">
          <template #reference>
            <el-button>高级筛选<span v-if="advancedCount" class="count">{{ advancedCount }}</span></el-button>
          </template>
          <div class="advanced">
            <div class="advanced__header">
              <strong>高级筛选</strong>
              <div>
                <el-button link @click="clearAdvanced">清空高级条件</el-button>
                <el-button link @click="advancedVisible = false">关闭</el-button>
              </div>
            </div>
            <el-form label-width="90px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"><el-form-item label="来源类型"><el-select v-model="searchForm.sourceType" clearable style="width: 100%" @change="search"><el-option v-for="(label, value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="请求类别"><el-select v-model="searchForm.requestCategory" clearable style="width: 100%" @change="search"><el-option v-for="(label, value) in categoryLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="searchForm.priority" clearable style="width: 100%" @change="search"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="负责人"><el-select v-model="searchForm.ownerId" clearable filterable style="width: 100%" @change="search"><el-option v-for="user in users" :key="user.id" :label="userName(user)" :value="user.id" /></el-select></el-form-item></el-col>
              </el-row>
            </el-form>
          </div>
        </el-popover>
      </div>

      <el-alert v-if="listError" class="list-error" type="error" show-icon :closable="false">
        <template #title>资源需求列表加载失败</template>
        <div class="list-error__content">
          <span>{{ listError }}</span>
          <el-button link type="primary" :loading="loading" @click="fetchData">重新加载</el-button>
        </div>
      </el-alert>

      <el-table ref="tableRef" :data="rows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange">
        <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
        <el-table-column type="index" label="序号" width="64" fixed="left" :index="rowIndex" />
        <el-table-column
          v-for="column in visibleColumns"
          :key="column.key"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :show-overflow-tooltip="column.tooltip !== false"
        >
          <template #default="{ row }">
            <span v-if="column.key === 'requestNo'">{{ row.requestNo || '-' }}</span>
            <span v-else-if="column.key === 'sourceType'">{{ sourceLabels[row.sourceType] || '-' }}</span>
            <span v-else-if="column.key === 'projectType'">{{ projectTypesText(row) }}</span>
            <el-tag v-else-if="column.key === 'projectStatus'" size="small" type="info">{{ projectStatusText(row) }}</el-tag>
            <span v-else-if="column.key === 'orderNo'">{{ row.currentOrderNo || row.sourceOrderNoSnapshot || '-' }}</span>
            <span v-else-if="column.key === 'projectName'">{{ row.currentProjectName || row.sourceProjectNameSnapshot || '-' }}</span>
            <span v-else-if="column.key === 'clientCode'">{{ row.clientCodeSnapshot || '-' }}</span>
            <span v-else-if="column.key === 'clientShortName'">{{ row.clientShortNameSnapshot || '-' }}</span>
            <LanguageItemsPopover v-else-if="column.key === 'languages'" :items="row.items || []" :languages="languages" mode="language" />
            <LanguageItemsPopover v-else-if="column.key === 'requiredCount'" :items="row.items || []" :languages="languages" mode="count" />
            <LanguageItemsPopover v-else-if="column.key === 'requestDetail'" :items="row.items || []" :languages="languages" mode="detail" :request-detail="row.requestDetail" />
            <el-tag v-else-if="column.key === 'priority'" :type="priorityType(row.priority)" size="small">{{ priorityLabels[row.priority] || '-' }}</el-tag>
            <span v-else-if="column.key === 'ownerName'">{{ ownerName(row) }}</span>
            <el-progress v-else-if="column.key === 'progress'" :percentage="row.progressPercent" :stroke-width="10" />
            <el-tag v-else-if="column.key === 'requestStatus'" :type="statusType(row.requestStatus)" size="small">{{ statusLabels[row.requestStatus] || '-' }}</el-tag>
            <span v-else-if="column.key === 'requestedAt'">{{ formatDate(row.requestedAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" width="90" fixed="right" align="center">
          <template #default="{ row }">
            <el-popover trigger="click" placement="left" :width="760" :fallback-placements="['bottom', 'top', 'right']" :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { padding: 16, boundary: 'viewport' } }] }" title="资源需求详情" popper-class="resource-detail-popover" @show="loadDetail(row)">
              <template #reference><el-button link type="primary">查看详情</el-button></template>
              <div class="detail" v-loading="detailLoading === row.id">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="请求编号">{{ detailOf(row).requestNo || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="项目类型">{{ projectTypesText(detailOf(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="项目状态">{{ projectStatusText(detailOf(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="请求状态">{{ statusLabels[detailOf(row).requestStatus] || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="需求项目订单号">{{ detailOf(row).currentOrderNo || detailOf(row).sourceOrderNoSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="需求项目">{{ detailOf(row).currentProjectName || detailOf(row).sourceProjectNameSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="客户编号">{{ detailOf(row).clientCodeSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="客户简称">{{ detailOf(row).clientShortNameSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="负责人">{{ ownerName(detailOf(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="优先级">{{ priorityLabels[detailOf(row).priority] || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="发起时间">{{ formatDate(detailOf(row).requestedAt) }}</el-descriptions-item>
                  <el-descriptions-item v-if="detailOf(row).requestDetail" label="需求详情" :span="2"><div class="pre">{{ detailOf(row).requestDetail }}</div></el-descriptions-item>
                  <el-descriptions-item label="语种、人数及要求" :span="2"><LanguageItemsPopover :items="detailOf(row).items || []" :languages="languages" mode="all" :request-detail="detailOf(row).requestDetail" :always-expanded="true" /></el-descriptions-item>
                </el-descriptions>
              </div>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column v-if="canWrite && !deleteMode" label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openProgress(row)">更新进度</el-button>
            <el-button link type="primary" @click="openEditor(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pagination" v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" layout="total, sizes, prev, pager, next" @change="fetchData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑资源需求' : '新增资源需求'" width="min(960px, calc(100vw - 32px))" top="5vh" class="resource-dialog" @closed="resetEditor">
      <el-form ref="formRef" :model="form" :rules="formRules" :validate-on-rule-change="false" label-width="110px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12"><el-form-item label="项目类型" prop="sourceType"><el-select v-model="form.sourceType" style="width: 100%" @change="sourceChanged"><el-option v-for="(label, value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="12"><el-form-item label="请求类别" prop="requestCategory"><el-select v-model="form.requestCategory" style="width: 100%"><el-option v-for="item in availableCategories" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item v-if="form.sourceType !== 'other'" label="来源项目" prop="sourceProjectId">
          <el-select v-model="form.sourceProjectId" filterable style="width: 100%" :loading="prefillLoading" @change="sourceProjectChanged">
            <el-option v-for="item in availableProjects" :key="item.id" :label="item.projectName || '未命名'" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="其他类型" prop="otherProjectTypes">
          <el-select v-model="form.otherProjectTypes" multiple filterable allow-create default-first-option style="width: 100%" placeholder="输入其他类型后按回车，可添加多个">
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>

        <el-descriptions v-if="sourceInfo.projectName" class="source-summary" title="自动获取的项目信息" :column="2" border size="small">
          <el-descriptions-item label="项目类型">{{ sourceInfo.projectTypes.map(projectTypeLabel).join('、') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">{{ projectStatusLabel(sourceInfo.projectStatus) }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ sourceInfo.orderNo || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ sourceInfo.projectName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户编号">{{ sourceInfo.clientCode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ sourceInfo.clientShortName || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="16">
          <el-col :xs="24" :md="8"><el-form-item label="优先级"><el-select v-model="form.priority" style="width: 100%"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="8"><el-form-item label="请求状态"><el-select v-model="form.requestStatus" style="width: 100%"><el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="8"><el-form-item label="负责人"><el-select v-model="form.ownerId" clearable filterable style="width: 100%"><el-option v-for="user in users" :key="user.id" :label="userName(user)" :value="user.id" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item v-if="form.requestDetail || showRequestDetail" label="需求详情">
          <el-input v-model="form.requestDetail" type="textarea" :rows="4" placeholder="已从来源项目自动获取，可继续补充；无内容时列表自动隐藏" />
        </el-form-item>
        <div v-else class="show-detail-row"><el-button link type="primary" @click="showRequestDetail = true">补充需求详情</el-button></div>

        <section class="items">
          <div class="section-title">
            <div><strong>需求语种、人数及详情</strong><div class="section-hint">已自动获取来源项目内容；方言或未收录语种可直接输入后创建。</div></div>
            <el-button type="primary" plain @click="addItem">添加明细</el-button>
          </div>
          <el-empty v-if="!form.items.length" description="暂无结构化明细" :image-size="64" />
          <div v-for="(item, index) in form.items" :key="item.id || index" class="item-card">
            <div class="item-title"><span>明细 {{ index + 1 }}</span><el-button link type="danger" @click="form.items.splice(index, 1)">删除</el-button></div>
            <el-row :gutter="12">
              <el-col :xs="24" :md="8"><el-select v-model="item.sourceLanguageId" clearable filterable allow-create default-first-option placeholder="需求语种/源语种" style="width: 100%"><el-option v-for="language in languages" :key="language.id" :label="languageOptionLabel(language)" :value="language.id" /></el-select></el-col>
              <el-col :xs="24" :md="8"><el-select v-model="item.targetLanguageId" clearable filterable allow-create default-first-option placeholder="目标语种（可空）" style="width: 100%"><el-option v-for="language in languages" :key="language.id" :label="languageOptionLabel(language)" :value="language.id" /></el-select></el-col>
              <el-col :xs="24" :md="8"><el-input-number v-model="item.requiredCount" :min="1" placeholder="需求人数（可空）" style="width: 100%" /></el-col>
            </el-row>
            <el-input v-model="item.requirementDetail" type="textarea" :rows="2" placeholder="该语种具体要求；完整需求默认放在第一条明细" style="margin-top: 10px" />
          </div>
        </section>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="progressDialog" title="更新资源开拓进度" width="min(520px, calc(100vw - 32px))">
      <el-form label-width="90px"><el-form-item label="完成比例"><el-slider v-model="progressForm.progressPercent" show-input /></el-form-item><el-form-item label="进度说明"><el-input v-model="progressForm.progressNote" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="progressDialog = false">取消</el-button><el-button type="primary" @click="saveProgress">保存进度</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElMessage, ElPopover, ElTable, ElTableColumn } from 'element-plus'
import * as api from '@/api/resourceRequests'
import { getAnnotationProjects } from '@/api/annotationProjects'
import { getRecruitmentProjects } from '@/api/recruitmentProjects'
import { getInterpretationProjects } from '@/api/interpretationProjects'
import { getProjects as getTranslationProjects } from '@/api/projects'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'
import { getUsers } from '@/api/users'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { hasPermission } from '@/utils/permission'

const languageText = (items, languages) => {
  const label = (id) => languages.find((item) => item.id === id)?.label || '-'
  return items.map((item) => `${label(item.sourceLanguageId)}${item.targetLanguageId ? ` → ${label(item.targetLanguageId)}` : ''}`)
}

const LanguageItemsPopover = defineComponent({
  props: { items: { type: Array, default: () => [] }, languages: { type: Array, default: () => [] }, mode: { type: String, default: 'all' }, requestDetail: { type: String, default: '' }, alwaysExpanded: Boolean },
  setup(props) {
    const rows = computed(() => props.items.map((item, index) => ({ ...item, sequence: index + 1, language: languageText([item], props.languages)[0] })))
    const summary = computed(() => {
      if (props.mode === 'language') return languageText(props.items, props.languages).join('、') || '-'
      if (props.mode === 'count') return props.items.map((item, index) => item.requiredCount ? `${languageText([item], props.languages)[0]} ${item.requiredCount}人` : (index === 0 ? '-' : '')).filter(Boolean).join('、') || '-'
      if (props.mode === 'detail') return props.requestDetail || props.items.find((item) => item.requirementDetail)?.requirementDetail || '-'
      return '-'
    })
    const table = () => h(ElTable, { data: rows.value, border: true, size: 'small', maxHeight: 360 }, () => [
      h(ElTableColumn, { prop: 'sequence', label: '序号', width: 58 }),
      h(ElTableColumn, { prop: 'language', label: '需求语种', minWidth: 170 }),
      h(ElTableColumn, { label: '需求人数', width: 90 }, { default: ({ row }) => row.requiredCount ? `${row.requiredCount} 人` : '-' }),
      h(ElTableColumn, { label: '需求详情', minWidth: 220 }, { default: ({ row }) => row.requirementDetail || '-' }),
    ])
    return () => {
      if (props.alwaysExpanded) return props.items.length ? table() : h('span', '-')
      if (props.items.length <= 1) return h('span', { class: 'cell-summary' }, summary.value)
      return h(ElPopover, { trigger: 'click', placement: 'left', width: 680, popperClass: 'resource-items-popover' }, { reference: () => h(ElButton, { link: true, type: 'primary' }, () => summary.value), default: table })
    }
  },
})

const route = useRoute()
const router = useRouter()
const rows = ref([])
const users = ref([])
const languages = ref([])
const projects = reactive({ annotation: [], recruitment: [], interpretation: [], translation: [] })
const loading = ref(false)
const listError = ref('')
const prefillLoading = ref(false)
const advancedVisible = ref(false)
const advancedWidth = ref(760)
const dialogVisible = ref(false)
const progressDialog = ref(false)
const saving = ref(false)
let submitLocked = false
const detailLoading = ref('')
const detailCache = reactive({})
const showRequestDetail = ref(false)
const formRef = ref(null)
const pagination = reactive({ page: 1, limit: 10, total: 0 })
const tableRef = ref(null)
const canWrite = hasPermission('projects:write')
const searchForm = reactive({ keyword: '', requestStatus: '', sourceType: '', requestCategory: '', priority: '', ownerId: '' })
const form = reactive({})
const sourceInfo = reactive({ projectTypes: [], orderNo: '', projectName: '', projectStatus: '', clientCode: '', clientShortName: '' })
const progressForm = reactive({ id: '', progressPercent: 0, progressNote: '' })

const sourceLabels = { annotation: '标注', recruitment: '招聘', interpretation: '口译', translation: '笔译', other: '其他' }
const categoryLabels = { annotation_trial: '标注试标', annotation_formal: '标注正式', recruitment: '招聘', interpretation: '口译', translation: '笔译', other: '其他' }
const statusLabels = { draft: '草稿', submitted: '已提交', in_progress: '进行中', fulfilled: '已完成', cancelled: '已取消' }
const priorityLabels = { high: '高', medium: '中', low: '低' }
const projectTypeLabels = {
  audio_collection: '音频采集', audio_annotation: '音频标注', audio_evaluation: '音频评测', text_evaluation: '文本评测', text_annotation: '文本标注', quality_inspection: '质检', listening_test: '测听', slot_deduction: '扣槽', generalization: '泛化', translation: '翻译',
  onsite: '现场口译', booth: '展会摊位口译', exhibition_escort: '展会陪同口译', escort: '陪同口译', small_business_meeting: '小型商务会议口译', consecutive: '会议交传口译', simultaneous: '会议同传口译', online_meeting: '线上会议口译', online_simultaneous: '线上同传口译',
}
const projectStatusLabels = {
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果', resource_sourcing: '资源开拓', resource_sourcing_cancelled: '取消资源开拓', trial_preparation: '试标准备', trial_in_progress: '试标中', trial_passed: '试标通过', trial_failed: '试标未通过', trial_partially_passed: '部分试标通过', project_in_progress: '项目进行中', sent_to_client: '已发客户', client_feedback: '客户反馈', partially_cancelled: '已部分取消',
  pending_setup: '待启动', sourcing: '寻访中', recommending: '推荐中', interviewing: '面试中', offer_negotiation: 'Offer协商中', pending_onboard: '待入职', probation: '试用期', closed: '已关闭',
  initial_follow_up: '初步跟进中', in_progress: '进行中', ended: '已结束', settled: '已结款', active: '进行中', completed: '已完成', cancelled: '已取消',
  pending_confirmation: '待确认', confirmed: '已确认', organized: '已整理', translator_assigned: '已排译员', sent_to_translator: '已发译员', translator_returned: '译员发回', special_checked: '已专检', typeset: '已排版', special_checked_typeset: '已专检排版', reviewed: '已审核', feedback_sent_to_client: '反馈后发客户', paused: '已暂停',
}

const tableColumns = [
  { key: 'requestNo', label: '请求编号', width: 130 },
  { key: 'sourceType', label: '来源', width: 82 },
  { key: 'projectType', label: '项目类型', minWidth: 120 },
  { key: 'projectStatus', label: '项目状态', width: 110 },
  { key: 'orderNo', label: '需求项目订单号', width: 145 },
  { key: 'projectName', label: '需求项目', minWidth: 190 },
  { key: 'clientCode', label: '客户编号', width: 120 },
  { key: 'clientShortName', label: '客户简称', width: 110 },
  { key: 'ownerName', label: '负责人', width: 110 },
  { key: 'languages', label: '需求语种', minWidth: 170 },
  { key: 'requiredCount', label: '需求人数', minWidth: 135 },
  { key: 'requestDetail', label: '需求详情', minWidth: 180 },
  { key: 'priority', label: '优先级', width: 78 },
  { key: 'progress', label: '进度', width: 145, tooltip: false },
  { key: 'requestStatus', label: '请求状态', width: 100 },
  { key: 'requestedAt', label: '发起时间', width: 165 },
]
const defaultColumnKeys = ['projectType', 'projectStatus', 'projectName', 'clientShortName', 'languages', 'requiredCount', 'requestDetail']
const { selectedKeys: selectedColumnKeys, reset: resetColumns } = useTableColumns('resource-requests', tableColumns, defaultColumnKeys)
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination,deleteRow:(row)=>api.deleteResourceRequest(row.id),getLabel:(row)=>row.requestNo||row.currentProjectName||row.id,reload:()=>fetchData(),onDeleted:(row)=>{delete detailCache[row.id]},entityName:'资源需求'})
const visibleColumns = computed(() => tableColumns.filter((column) => selectedColumnKeys.value.includes(column.key)))
const advancedCount = computed(() => [searchForm.sourceType, searchForm.requestCategory, searchForm.priority, searchForm.ownerId].filter(Boolean).length)
const availableProjects = computed(() => projects[form.sourceType] || [])
const availableCategories = computed(() => form.sourceType === 'annotation' ? [{ value: 'annotation_trial', label: '标注试标' }, { value: 'annotation_formal', label: '标注正式' }] : [{ value: form.sourceType, label: sourceLabels[form.sourceType] }])
const formRules = computed(() => ({
  sourceType: [{ required: true, message: '请选择项目类型', trigger: 'change' }],
  requestCategory: [{ required: true, message: '请选择请求类别', trigger: 'change' }],
  sourceProjectId: [{ required: form.sourceType !== 'other', message: '请选择来源项目', trigger: 'change' }],
  otherProjectTypes: [{ type: 'array', required: form.sourceType === 'other', min: 1, message: '请至少填写一个其他类型', trigger: 'change' }],
}))

let timer
let controller
let requestId = 0
const emptyForm = () => ({ id: '', sourceType: 'annotation', requestCategory: 'annotation_trial', sourceProjectId: '', otherProjectTypes: [], requestDetail: '', priority: 'medium', requestStatus: 'submitted', ownerId: '', items: [] })
const resetSourceInfo = () => Object.assign(sourceInfo, { projectTypes: [], orderNo: '', projectName: '', projectStatus: '', clientCode: '', clientShortName: '' })
const params = () => ({ keyword: searchForm.keyword.trim() || undefined, request_status: searchForm.requestStatus || undefined, source_type: searchForm.sourceType || undefined, request_category: searchForm.requestCategory || undefined, priority: searchForm.priority || undefined, owner_id: searchForm.ownerId || undefined })
const fetchData = async () => {
  controller?.abort()
  controller = new AbortController()
  const current = ++requestId
  loading.value = true
  listError.value = ''
  try {
    const filters = params()
    const [list, count] = await Promise.all([
      api.getResourceRequests({ skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit, ...filters }, { signal: controller.signal }),
      api.getResourceRequestCount(filters, { signal: controller.signal }),
    ])
    if (current !== requestId) return
    rows.value = list
    pagination.total = count.total || 0
  } catch (error) {
    if (error.code !== 'ERR_CANCELED' && current === requestId) {
      listError.value = error.detail || '网络异常，资源需求列表未刷新，请检查网络后重试'
      ElMessage.error(listError.value)
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}
const search = () => { clearTimeout(timer); pagination.page = 1; fetchData() }
const onKeyword = (value) => { clearTimeout(timer); if (!value) return search(); timer = setTimeout(search, 400) }
const reset = () => { Object.assign(searchForm, { keyword: '', requestStatus: '', sourceType: '', requestCategory: '', priority: '', ownerId: '' }); search() }
const clearAdvanced = () => { Object.assign(searchForm, { sourceType: '', requestCategory: '', priority: '', ownerId: '' }); search() }
const updateAdvancedWidth = () => { advancedWidth.value = Math.max(280, Math.min(760, window.innerWidth - 32)) }
const rowIndex = (index) => (pagination.page - 1) * pagination.limit + index + 1
const userName = (user) => user.full_name || user.fullName || user.username
const ownerName = (row) => {
  const ownerId = row.ownerId || row.owner_id
  if (!ownerId) return '-'
  const user = users.value.find((item) => item.id === ownerId)
  return user ? userName(user) : '-'
}
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
const languageOptionLabel = (language) => language.isCustom ? `${language.label}（自定义）` : language.label
const priorityType = (value) => ({ high: 'danger', medium: 'warning', low: 'info' }[value])
const statusType = (value) => ({ draft: 'info', submitted: 'warning', in_progress: 'primary', fulfilled: 'success', cancelled: 'danger' }[value])
const projectTypeLabel = (value) => projectTypeLabels[value] || value || '-'
const projectStatusLabel = (value) => projectStatusLabels[value] || value || '-'
const projectTypesText = (row) => row.sourceProjectTypesSnapshot?.length ? row.sourceProjectTypesSnapshot.map(projectTypeLabel).join('、') : (categoryLabels[row.requestCategory] || sourceLabels[row.sourceType] || '-')
const projectStatusText = (row) => projectStatusLabel(row.currentProjectStatus || row.sourceStatusSnapshot)
const detailOf = (row) => detailCache[row.id] || row
const loadDetail = async (row) => {
  if (detailCache[row.id]) return
  detailLoading.value = row.id
  try {
    detailCache[row.id] = await api.getResourceRequest(row.id)
  } catch (error) {
    ElMessage.error(error.detail || '加载资源需求详情失败')
  } finally {
    detailLoading.value = ''
  }
}

const sourceChanged = () => { form.sourceProjectId = ''; form.otherProjectTypes = []; form.requestCategory = form.sourceType === 'annotation' ? 'annotation_trial' : form.sourceType; form.requestDetail = ''; form.items = []; showRequestDetail.value = false; resetSourceInfo(); nextTick(() => formRef.value?.clearValidate()) }
const sourceProjectChanged = async (projectId) => {
  if (!projectId) return resetSourceInfo()
  prefillLoading.value = true
  try {
    const value = await api.getResourceRequestSourcePrefill(form.sourceType, projectId)
    form.requestCategory = value.requestCategory || form.requestCategory
    Object.assign(sourceInfo, { projectTypes: value.sourceProjectTypes || [], orderNo: value.orderNo || '', projectName: value.projectName || '', projectStatus: value.projectStatus || '', clientCode: value.clientCode || '', clientShortName: value.clientShortName || '' })
    form.requestDetail = value.requestDetail || ''
    form.items = (value.items || []).map((item) => ({ id: null, sourceLanguageId: item.sourceLanguageId || null, targetLanguageId: item.targetLanguageId || null, requiredCount: item.requiredCount || null, requirementDetail: item.requirementDetail || '' }))
    showRequestDetail.value = Boolean(form.requestDetail)
  } catch (error) { ElMessage.error(error.detail || '自动获取项目需求信息失败') } finally { prefillLoading.value = false }
}
const openEditor = async (row = null, source = null) => {
  if (!row?.id) api.resetResourceRequestIdempotency()
  let value = row
  if (row?.id) value = await api.getResourceRequest(row.id)
  Object.assign(form, emptyForm(), value || {})
  resetSourceInfo()
  if (value) {
    form.sourceProjectId = value[`${value.sourceType}ProjectId`] || ''
    form.otherProjectTypes = value.sourceType === 'other' ? (value.otherSourceName || '').replaceAll('，', ',').split(',').map((item) => item.trim()).filter(Boolean) : []
    form.items = (value.items || []).map((item) => ({ ...item }))
    Object.assign(sourceInfo, { projectTypes: value.sourceProjectTypesSnapshot || [], orderNo: value.currentOrderNo || value.sourceOrderNoSnapshot || '', projectName: value.currentProjectName || value.sourceProjectNameSnapshot || '', projectStatus: value.currentProjectStatus || value.sourceStatusSnapshot || '', clientCode: value.clientCodeSnapshot || '', clientShortName: value.clientShortNameSnapshot || '' })
  }
  if (source) {
    form.sourceType = source.sourceType
    form.requestCategory = source.requestCategory || (source.sourceType === 'annotation' ? 'annotation_trial' : source.sourceType)
    form.sourceProjectId = source.sourceProjectId
  }
  showRequestDetail.value = Boolean(form.requestDetail)
  dialogVisible.value = true
  if (source?.sourceProjectId) await sourceProjectChanged(source.sourceProjectId)
}
const resetEditor = () => { formRef.value?.clearValidate(); Object.assign(form, emptyForm()); resetSourceInfo(); showRequestDetail.value = false }
const addItem = () => form.items.push({ id: null, sourceLanguageId: null, targetLanguageId: null, requiredCount: null, requirementDetail: '' })

const ensureLanguageId = async (value) => {
  if (!value) return null
  if (languages.value.some((item) => item.id === value)) return value
  const label = String(value).trim()
  const existing = languages.value.find((item) => item.label.toLowerCase() === label.toLowerCase())
  if (existing) return existing.id
  const created = await createProjectLanguage(label)
  languages.value.push(created)
  return created.id
}
const normalizeItems = async () => {
  const meaningful = form.items.filter((item) => item.sourceLanguageId || item.targetLanguageId || item.requiredCount || item.requirementDetail?.trim())
  return Promise.all(meaningful.map(async (item) => ({ ...item, sourceLanguageId: await ensureLanguageId(item.sourceLanguageId), targetLanguageId: await ensureLanguageId(item.targetLanguageId), requirementDetail: item.requirementDetail?.trim() || null })))
}
const payload = async () => {
  const data = { sourceType: form.sourceType, requestCategory: form.requestCategory, annotationProjectId: null, recruitmentProjectId: null, interpretationProjectId: null, translationProjectId: null, otherSourceName: form.sourceType === 'other' ? form.otherProjectTypes.map((item) => item.trim()).filter(Boolean).join(',') : null, requestDetail: form.requestDetail.trim(), priority: form.priority, requestStatus: form.requestStatus, ownerId: form.ownerId || null, items: await normalizeItems() }
  if (form.sourceType !== 'other') data[`${form.sourceType}ProjectId`] = form.sourceProjectId
  return data
}
const scrollToFirstError = () => requestAnimationFrame(() => document.querySelector('.resource-dialog .el-form-item.is-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
const save = async () => {
  if (submitLocked) return
  submitLocked = true
  try { await formRef.value?.validate() } catch { submitLocked = false; scrollToFirstError(); return }
  saving.value = true
  try {
    const data = await payload()
    const saved = form.id ? await api.updateResourceRequest(form.id, data) : await api.createResourceRequest(data)
    delete detailCache[saved.id]
    dialogVisible.value = false
    ElMessage.success('资源需求已保存')
    await fetchData()
  } catch (error) { ElMessage.error(error.detail || '保存失败') } finally { saving.value = false; submitLocked = false }
}
const openProgress = (row) => { Object.assign(progressForm, { id: row.id, progressPercent: row.progressPercent, progressNote: '' }); progressDialog.value = true }
const saveProgress = async () => { try { await api.updateResourceProgress(progressForm.id, progressForm); delete detailCache[progressForm.id]; progressDialog.value = false; ElMessage.success('进度已更新'); await fetchData() } catch (error) { ElMessage.error(error.detail || '更新失败') } }

onMounted(async () => {
  updateAdvancedWidth()
  window.addEventListener('resize', updateAdvancedWidth)
  const results = await Promise.allSettled([getAnnotationProjects({ skip: 0, limit: 500 }), getRecruitmentProjects({ skip: 0, limit: 500 }), getInterpretationProjects({ skip: 0, limit: 500 }), getTranslationProjects({ skip: 0, limit: 500 }), getProjectLanguages(), getUsers({ skip: 0, limit: 500 })])
  projects.annotation = results[0].value || []
  projects.recruitment = results[1].value || []
  projects.interpretation = results[2].value || []
  projects.translation = results[3].value || []
  languages.value = results[4].value || []
  users.value = results[5].value || []
  Object.assign(form, emptyForm())
  await fetchData()
  const sourceType = String(route.query.sourceType || '')
  const sourceProjectId = String(route.query.sourceProjectId || '')
  if (sourceProjectId && Object.hasOwn(sourceLabels, sourceType) && sourceType !== 'other') {
    await openEditor(null, { sourceType, sourceProjectId, requestCategory: String(route.query.requestCategory || '') })
    const query = { ...route.query }
    delete query.sourceType
    delete query.sourceProjectId
    delete query.requestCategory
    await router.replace({ query })
  }
})
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort(); window.removeEventListener('resize', updateAdvancedWidth) })
</script>

<style scoped>
.resource-request-page { min-height: 0; }
.header, .header-actions, .filters, .advanced__header, .section-title, .item-title { display: flex; align-items: center; }
.header, .advanced__header, .section-title, .item-title { justify-content: space-between; }
.header-actions, .filters { gap: 8px; }
.header h2 { margin: 0; }
.header p { margin: 4px 0 0; color: var(--el-text-color-secondary); }
.filters { margin-bottom: 16px; flex-wrap: wrap; }
.list-error { margin-bottom: 16px; }
.list-error__content { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.count { margin-left: 5px; padding: 1px 6px; border-radius: 9px; color: #fff; background: var(--el-color-primary); font-size: 11px; }
.advanced { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.advanced__header { position: sticky; top: 0; z-index: 1; margin-bottom: 12px; background: var(--el-bg-color-overlay); }
.pagination { margin-top: 16px; }
.detail { max-height: 560px; overflow-y: auto; }
.pre { white-space: pre-wrap; word-break: break-word; }
.cell-summary { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-summary { margin-bottom: 16px; }
.items { padding: 14px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.section-hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; font-weight: normal; }
.item-card { margin-top: 12px; padding: 12px; border-radius: 6px; background: var(--el-fill-color-light); }
.item-title { margin-bottom: 10px; font-weight: 600; }
.show-detail-row { margin: -4px 0 12px 110px; }
@media (max-width: 767px) { .header { align-items: flex-start; flex-direction: column; gap: 12px; } .header-actions { width: 100%; flex-wrap: wrap; } .show-detail-row { margin-left: 0; } }
</style>

<style>
.resource-dialog { display: flex; max-height: 90vh; flex-direction: column; overflow: hidden; }
.resource-dialog .el-dialog__header, .resource-dialog .el-dialog__footer { flex-shrink: 0; }
.resource-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.resource-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); box-shadow: 0 -4px 12px rgb(0 0 0 / 4%); }
.resource-detail-popover, .resource-items-popover { max-width: calc(100vw - 32px) !important; }
@media (max-width: 768px) {
  .resource-detail-popover.el-popper, .resource-items-popover.el-popper {
    position: fixed !important;
    left: 16px !important;
    right: 16px !important;
    width: auto !important;
    max-width: none !important;
    transform: none !important;
  }
}
</style>
