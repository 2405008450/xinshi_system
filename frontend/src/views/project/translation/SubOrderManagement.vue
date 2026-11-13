<template>
  <el-card class="common-page-card compact-list-card suborder-management" :class="{'suborder-management--embedded':embedded}">
    <template #header>
      <div class="card-header">
        <div>
          <span class="page-title">子订单管理</span>
          <p class="page-subtitle">{{ project.orderNo || route.query.orderNo || '-' }} / {{ project.projectName || route.query.projectName || '-' }}</p>
        </div>
        <div class="header-actions">
          <el-button @click="structureVisible = true">子订单结构</el-button>
          <FolderImportRecords :project-id="projectId" />
          <el-button @click="downloadHierarchy">导出层级Excel</el-button>
          <el-button v-if="!embedded" @click="goBack">返回项目详情</el-button>
          <BatchDeleteToolbar
            v-if="canWriteProjects"
            :active="deleteMode"
            :selected-count="selectedRows.length"
            :loading="deleting"
            @enter="enterDeleteMode"
            @exit="exitDeleteMode"
            @confirm="confirmBatchDelete"
          />
          <el-button v-if="canWriteProjects && !deleteMode" type="primary" @click="openCreateDialog">小量新增</el-button>
          <el-button v-if="canWriteProjects && !deleteMode" @click="openBatchDialog('quantity')">按数量批量新增</el-button>
          <el-button v-if="canWriteProjects && !deleteMode" @click="openBatchDialog('unc')">读取路径</el-button>
          <el-button v-if="canWriteProjects && !deleteMode" @click="openBatchDialog('filenames')">复制/文件导入</el-button>
          <el-button v-if="canWriteProjects && !deleteMode" @click="replacePathsVisible = true">批量替换路径</el-button>
        </div>
      </div>
    </template>

    <p class="copyable-order-path">根路径：{{ project.networkFilePath || '未登记' }}</p>
    <MotherSplitReviewNotice :review="project.motherSplitReview" @edit="editMother" />
    <div class="suborder-search">
      <el-input v-model="searchInput" clearable placeholder="搜索子订单号、文件名称或路径" aria-label="搜索子订单" @input="queueSearch" @keyup.enter="applySearch" />
      <el-button type="primary" @click="applySearch">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
      <span v-if="searchKeyword">匹配 {{ filteredSubOrders.length }} / {{ subOrders.length }} 条</span>
    </div>
    <VerticalSplitPanels top-label="统计填写区" bottom-label="子订单列表">
    <template #top>
    <SubOrderStatisticsGrid :root-path="project.networkFilePath" :rows="subOrders" :visible-rows="filteredSubOrders" :editable="canWriteProjects && !deleteMode" @saved="fetchSubOrders" />
    </template>
    <template #bottom>
    <div class="suborder-list-region">
    <el-table class="suborder-management-table" height="100%" scrollbar-always-on ref="subOrderTableRef" :data="filteredSubOrders" v-loading="loading" row-key="id" border @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="子订单号" min-width="180">
        <template #header>
          <ClickableColumnHeader label="子订单号" hint="点击子订单号查看详情" />
        </template>
        <template #default="{ row }">
          <BusinessDetailPopover :row="row" title="子订单详情" :items="subOrderDetailItems" :status-label="getStatusLabel" :status-type="getStatusType">
            <template #reference>
              <el-button type="primary" link class="sub-order-no-link" :title="`${row.subOrderNo}（点击查看详情）`" @click.stop>
                {{ row.subOrderNo || '-' }}
              </el-button>
            </template>
          </BusinessDetailPopover>
        </template>
      </el-table-column>
      <el-table-column min-width="240">
        <template #header>
          <div class="sub-order-name-header">
            <span>文件名称</span>
            <el-button
              v-if="canWriteProjects && !deleteMode"
              type="primary"
              link
              size="small"
              :icon="Check"
              :loading="inlineSaving"
              :disabled="inlinePendingCount === 0"
              title="保存全部文件名称"
              @click="saveAllInlineNames"
            >保存全部{{ inlinePendingCount ? `（${inlinePendingCount}）` : '' }}</el-button>
          </div>
        </template>
        <template #default="{ row }">
          <InlineSubProjectName
            :sub-order-id="row.id"
            :model-value="row.subProjectName"
            :editable="canWriteProjects"
            :allow-missing-extension="!!row.folderInfo"
            @pending-change="handleInlinePendingChange(row, $event)"
            @saved="handleInlineSubOrderSaved(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="完整路径" min-width="340"><template #default="{row}"><span class="copyable-order-path">{{ row.networkFilePath || '-' }}</span><el-button v-if="row.networkFilePath" link @click="copyPath(row.networkFilePath)">复制</el-button></template></el-table-column>
      <el-table-column prop="languagePair" label="翻译方向" min-width="120" />
      <el-table-column label="字数统计" min-width="220">
        <template #default="{ row }">
          <div class="word-count-summary">
            <div>
              <div>{{ formatWordCountMatrix(displayedMatrices.get(row.id)) }}</div>
              <OrderWordCountSource :order="row" />
            </div>
            <WordCountMatrixPopover
              v-model="row.wordCountMatrix"
              entity-type="suborder"
              :entity-id="row.id"
              title="子订单字数统计"
              @saved="fetchSubOrders"
            />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="译员回稿时间" min-width="210">
        <template #header>
          <ClickableColumnHeader label="译员回稿时间" hint="点击回稿时间编辑译员任务完成情况及价格" />
        </template>
        <template #default="{ row }">
          <TranslatorCompletionPopover
            :translators="row.assignedTranslators"
            :status="row.status"
            :editable="canWriteProjects"
            :save="(completions) => saveSubOrderTranslatorCompletions(row, completions)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" min-width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="canWriteProjects && !deleteMode" label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <PrimaryEditButton @click="openEditDialog(row)" />
        </template>
      </el-table-column>
    </el-table>
    </div>
    </template>
    </VerticalSplitPanels>

    <DraggableFormDialog
      v-model="dialogVisible"
      class="suborder-editor-dialog"
      :title="dialogTitle"
      width="min(900px, calc(100vw - 32px))"
      top="5vh"
      @closed="resetSubOrderForm"
    >
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="dialogTitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="subOrderEditorBodyRef">
      <AppForm number-scope="translation_suborder" number-field="subOrderNo" :number-active="dialogVisible && !subOrderForm.id" :number-parent="subOrderForm.parentSubOrderId || projectId" ref="subOrderFormRef" :model="subOrderForm" :rules="subOrderRules" label-width="130px">
        <OrderWordCountSource :order="subOrders.find(row => row.id === subOrderForm.id)" />
        <WordCountMatrixForm v-model="subOrderForm.wordCountMatrix" :aggregated="subOrderForm.wordCountMatrixSource === 'suborder_aggregate'" />
                <OriginalProjectInformation :value="subOrderForm.originalProjectInformation" />
        <el-form-item v-if="!subOrderForm.id" label="上级订单"><el-select v-model="subOrderForm.parentSubOrderId" clearable placeholder="母订单（创建一级子订单）"><el-option v-for="row in subOrders.filter(item=>item.subOrderNo.split('.').length<5)" :key="row.id" :value="row.id" :label="row.subOrderNo+' / '+row.subProjectName" /></el-select></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="母订单号"><el-input :model-value="project.orderNo || route.query.orderNo" disabled /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="子订单号"><ReadonlyField :model-value="subOrderForm.subOrderNo" source="auto" placeholder="保存后自动生成" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="文件名称" prop="subProjectName"><el-input v-model="subOrderForm.subProjectName" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="subOrderForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><OrderFieldHint :order="subOrderForm" field="status" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="文本类型"><el-input v-model="subOrderForm.fileTypeSecondary" /><OrderFieldHint :order="subOrderForm" field="fileTypeSecondary" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="翻译方向"><LanguagePairSelect allow-proofreading v-model="subOrderForm.languagePair" :single="(subOrderForm.subOrderNo || '').split('.').length > 5" :show-hint="false" /><div>文件订单多选方向后生成下级子订单，共用原文路径。文件夹保留原层级。</div><OrderFieldHint :order="subOrderForm" field="languagePair" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="优先级"><el-select v-model="subOrderForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="价格与付款"><el-button type="primary" plain @click="customerFinanceEditorRef.openForForm(subOrderForm,project)">价格与付款</el-button></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="subOrderForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /><OrderFieldHint :order="subOrderForm" field="customerDeadlineTime" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="subOrderForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="subOrderForm.translatorId" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员分配时间"><el-date-picker v-model="subOrderForm.translatorAssignmentTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="译员回稿时间">
              <TranslatorCompletionPopover
                :translators="subOrderForm.assignedTranslators"
                :status="subOrderForm.status"
                :editable="canWriteProjects"
                placement="bottom-start"
                :save="(completions) => saveSubOrderTranslatorCompletions(subOrderForm, completions)"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-collapse v-model="subOrderExpandedSections" class="suborder-progress-collapse">
          <el-collapse-item title="进度跟踪" name="progress">
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="译员交付进度"><el-input v-model="subOrderForm.translatorDeliveryProgress" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="审校前QC"><el-input v-model="subOrderForm.preReviewQcProgress" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="审校1"><el-input v-model="subOrderForm.review1Progress" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="审校2"><el-input v-model="subOrderForm.review2Progress" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="审校后QC"><el-input v-model="subOrderForm.postReviewQcProgress" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="排版进度"><el-input v-model="subOrderForm.layoutProgress" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="整合进度"><el-input v-model="subOrderForm.consolidationProgress" /></el-form-item></el-col>
        </el-row>
          </el-collapse-item>
        </el-collapse>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="文件路径"><el-input v-model="subOrderForm.networkFilePath" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="客户反馈"><el-input v-model="subOrderForm.clientFeedback" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><OrderInheritedExtras :model="subOrderForm" /></el-col>
        </el-row>
      </AppForm>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </DraggableFormDialog>

    <SubOrderStructureDialog v-model="structureVisible" :project-id="projectId" />
    <ReplaceSubOrderPathsDialog v-model="replacePathsVisible" :project-id="projectId"
      :root-path="project.networkFilePath" @saved="loadData" />
    <SubOrderBatchCreateDialog
      v-model="batchDialogVisible"
      :project="project"
      :initial-mode="batchDialogMode"
      :existing-names="subOrders.map((item) => item.subProjectName).filter(Boolean)"
      @created="afterBatchCreated"
    />
    <MotherEditor v-if="motherEditorVisible" editor-only :editor-project-id="projectId" @editor-closed="motherEditorVisible=false;loadData()" />
    <TranslationCustomerFinance ref="customerFinanceEditorRef" editor-only />
  </el-card>
</template>

<script setup>
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import OrderFieldHint from './components/OrderFieldHint.vue'
import OrderInheritedExtras from './components/OrderInheritedExtras.vue'
import VerticalSplitPanels from '@/components/common/VerticalSplitPanels.vue'
import FolderImportRecords from './components/FolderImportRecords.vue'
import SubOrderStatisticsGrid from './components/SubOrderStatisticsGrid.vue'
import SubOrderStructureDialog from './components/SubOrderStructureDialog.vue'
import { getProjectStatusOptions } from '@/utils/projectStatus'
import { validateTranslationFileName } from '@/utils/translationFileName'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, defineAsyncComponent } from 'vue'
import { matchesSearchFields } from '@/utils/searchMatching'
import { rollUpPendingRows } from '@/utils/translationChildSubmission'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import { getProject } from '@/api/projects'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder,exportSubOrderTree } from '@/api/subOrders'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import OrderWordCountSource from '@/components/common/OrderWordCountSource.vue'
import TranslationCustomerFinance from './CustomerFinance.vue'
import {projectFinanceFields} from '@/utils/projectFinanceFields'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import InlineSubProjectName from './components/InlineSubProjectName.vue'
import SubOrderBatchCreateDialog from './components/SubOrderBatchCreateDialog.vue'
import ReplaceSubOrderPathsDialog from './components/ReplaceSubOrderPathsDialog.vue'
import WordCountMatrixForm from '@/components/common/WordCountMatrixForm.vue'
import MotherSplitReviewNotice from './components/MotherSplitReviewNotice.vue'
import OriginalProjectInformation from './components/OriginalProjectInformation.vue'
const MotherEditor=defineAsyncComponent(()=>import('./ProjectDetails.vue'))
const motherEditorVisible=ref(false)
const emit=defineEmits(['edit-mother'])
function editMother(){if(props.embedded)emit('edit-mother');else motherEditorVisible.value=true}
import TranslatorCompletionPopover from './components/TranslatorCompletionPopover.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { createEmptyWordCountMatrix, formatWordCountMatrix, normalizeWordCountMatrix } from '@/utils/wordCountMatrix'
import { formatBusinessDateTime } from '@/utils/deadlineDisplay'
import { hasPermission } from '@/utils/permission'

const props=defineProps({projectId:String,embedded:Boolean})
const route = useRoute()
const router = useRouter()
const canWriteProjects = hasPermission('projects:write')
const projectId = props.projectId || route.params.projectId
const loading = ref(false)
const dialogVisible = ref(false)
const subOrderExpandedSections = ref([])
const batchDialogVisible = ref(false)
const replacePathsVisible = ref(false)
const structureVisible = ref(false)
const batchDialogMode=ref('quantity')
const inlineChanges = ref(new Map())
const inlineSaving = ref(false)
const dialogTitle = ref('小量新增')
const subOrderFormRef = ref(null)
const subOrderEditorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(subOrderEditorBodyRef)
const subOrderTableRef = ref(null)
const subOrders = ref([])
const displayedMatrices = computed(() => {
  const rows = subOrders.value.map(row => ({
    ...row, wordCountMatrix: normalizeWordCountMatrix(row.wordCountMatrix)
  }))
  rollUpPendingRows(rows)
  return new Map(rows.map(row => [row.id, row.wordCountMatrix]))
})
const searchInput = ref('')
const searchKeyword = ref('')
let searchTimer
const filteredSubOrders = computed(() => {
  const keyword = searchKeyword.value
  if (!keyword) return subOrders.value
  return subOrders.value.filter(row => matchesSearchFields(
    [row.subOrderNo, row.subProjectName, row.networkFilePath], keyword
  ))
})
function applySearch() {
  clearTimeout(searchTimer)
  const keyword = searchInput.value.trim()
  if (keyword !== searchKeyword.value) {
    subOrderTableRef.value?.clearSelection()
    searchKeyword.value = keyword
  }
}
function queueSearch() {
  clearTimeout(searchTimer)
  if (!searchInput.value.trim()) applySearch()
  else searchTimer = setTimeout(applySearch, 400)
}
function resetSearch() {
  searchInput.value = ''
  applySearch()
}
onBeforeUnmount(() => clearTimeout(searchTimer))
const inlinePendingCount = computed(() => inlineChanges.value.size)
const project = reactive({ childFieldDifferences:{}, serviceContent:'', customerRequirementProfessional:'', customerRequirementSpecial:'', remarks:'', id: '', orderNo: '', projectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), projectStatus: 'pending_confirmation', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorAssignmentTime: '', translatorDeliveryProgress: '', preReviewQcProgress: '', review1Progress: '', review2Progress: '', postReviewQcProgress: '', layoutProgress: '', consolidationProgress: '', networkFilePath: '' })
const createSubOrderForm = () => ({ serviceContent:'', customerRequirementProfessional:'', customerRequirementSpecial:'', inheritedFields:[], childFieldDifferences:{}, id: '', parentSubOrderId: '', parentProjectId: projectId, subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), wordCountMatrixSource: 'suborder', customerChargeItems: [], customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', status: 'pending_confirmation', translatorDeliveryProgress: '', preReviewQcProgress: '', review1Progress: '', review2Progress: '', postReviewQcProgress: '', layoutProgress: '', consolidationProgress: '', networkFilePath: '', remarks: '' })
const subOrderForm = reactive(createSubOrderForm())
const projectStatusOptions = getProjectStatusOptions('translation')
const priorityOptions = ['低', '中', '高', '紧急']
const subOrderRules = { subProjectName: [{ required: true, validator: (rule,value,callback)=>subOrderForm.folderInfo?callback(value?.trim()?undefined:new Error('请填写文件夹名称')):validateTranslationFileName(rule,value,callback), trigger: ['blur','change'] }] }
const NULLABLE_FIELDS = ['subProjectName', 'fileTypeSecondary', 'languagePair', 'priority', 'customerDeadlineTime', 'sentToClientTime', 'clientFeedback', 'translatorId', 'translatorAssignmentTime', 'translatorDeliveryProgress', 'preReviewQcProgress', 'review1Progress', 'review2Progress', 'postReviewQcProgress', 'layoutProgress', 'consolidationProgress', 'networkFilePath', 'remarks']
const formatTranslatorReturnTimes = (items) => {
  if (!Array.isArray(items) || !items.length) return '-'
  const values = items.map((item) => {
    const time = item.translatorReturnTime || item.translator_return_time
    if (!time) return ''
    const name = item.translatorName || item.translator_name || '译员'
    return `${name}：${formatBusinessDateTime(time)}`
  }).filter(Boolean)
  return values.length ? values.join('；') : '-'
}
const subOrderDetailItems = [
  { label: '子订单号', key: 'subOrderNo' }, { label: '文件名称', key: 'subProjectName' },
  { label: '状态', key: 'status', type: 'status' }, { label: '文件二级类型', key: 'fileTypeSecondary' }, { label: '翻译方向', key: 'languagePair' }, { label: '优先级', key: 'priority' },
  { label: '字数统计', key: 'wordCountMatrix', formatter: formatWordCountMatrix }, { label: '客户交稿时间', key: 'customerDeadlineTime' }, { label: '发客户时间', key: 'sentToClientTime' }, { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '译员分配时间', key: 'translatorAssignmentTime' }, { label: '译员回稿时间', key: 'translatorReturnTime', span: 2, formatter: (_value, row) => formatTranslatorReturnTimes(row.assignedTranslators) },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' }, { label: '审校前QC', key: 'preReviewQcProgress' }, { label: '审校1', key: 'review1Progress' }, { label: '审校2', key: 'review2Progress' },
  { label: '审校后QC', key: 'postReviewQcProgress' }, { label: '排版进度', key: 'layoutProgress' }, { label: '整合进度', key: 'consolidationProgress' }, { label: '文件路径', key: 'networkFilePath', span: 2 },
  { label: '备注', key: 'remarks', span: 2 }, { label: '创建时间', key: 'createdAt' }, { label: '更新时间', key: 'updatedAt' }
]
const legacyStatusMap = { pending: 'pending_confirmation', in_progress: 'confirmed', completed: 'sent_to_client', terminated: 'cancelled' }
const normalizeStatus = (status) => legacyStatusMap[status] || status
const getStatusLabel = (status) => projectStatusOptions.find(item => item.value === normalizeStatus(status))?.label || status || '-'
const getStatusType = (status) => ({ pending_confirmation: 'info', confirmed: 'primary', organized: 'primary', translator_assigned: 'warning', sent_to_translator: 'warning', translator_returned: 'primary', special_checked: 'primary', typeset: 'primary', special_checked_typeset: 'primary', reviewed: 'success', sent_to_client: 'success', client_feedback: 'success', feedback_sent_to_client: 'success', cancelled: 'danger', partially_cancelled: 'danger', paused: 'warning' }[normalizeStatus(status)] || 'info')
const cloneValue = (value) => value && typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value
const assignReactive = (target, values) => { Object.keys(target).forEach((key) => { target[key] = cloneValue(values[key] ?? target[key]) }) }
const cleanPayload = (payload) => { const result = { ...payload }; NULLABLE_FIELDS.forEach((key) => { if (result[key] === '') result[key] = null }); return result }
const buildDefaultsFromProject = () => ({ serviceContent:project.serviceContent, customerRequirementProfessional:project.customerRequirementProfessional, customerRequirementSpecial:project.customerRequirementSpecial, remarks:project.remarks, fileTypeSecondary: project.fileTypeSecondary, languagePair: project.languagePair, priority: project.priority, wordCountMatrix: createEmptyWordCountMatrix(), customerChargeItems: [], customerDeadlineTime: project.customerDeadlineTime, sentToClientTime: project.sentToClientTime, clientFeedback: project.clientFeedback, translatorId: project.translatorId, translatorAssignmentTime: project.translatorAssignmentTime, status: normalizeStatus(project.projectStatus) || 'pending_confirmation', translatorDeliveryProgress: project.translatorDeliveryProgress, preReviewQcProgress: project.preReviewQcProgress, review1Progress: project.review1Progress, review2Progress: project.review2Progress, postReviewQcProgress: project.postReviewQcProgress, layoutProgress: project.layoutProgress, consolidationProgress: project.consolidationProgress, networkFilePath: project.networkFilePath })
const fetchProject = async () => { const response = await getProject(projectId); assignReactive(project, { ...project, ...response }) }
let subOrderRequest = 0
const fetchSubOrders = async () => {
  const request = ++subOrderRequest
  const response = await getSubOrdersByProject(projectId)
  if (request !== subOrderRequest) return
  subOrders.value = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []
  inlineChanges.value = new Map()
}
const loadData = async () => { loading.value = true; try { await Promise.all([fetchProject(), fetchSubOrders()]) } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '加载子订单失败')) } finally { loading.value = false } }
const goBack = () => router.push({ name: 'TranslationProjectDetails' })
const resetSubOrderForm = () => { subOrderExpandedSections.value = []; assignReactive(subOrderForm, createSubOrderForm()); subOrderFormRef.value?.clearValidate() }
const afterBatchCreated=async()=>{await loadData();if(project.motherSplitReview?.required)editMother()}
const openCreateDialog = () => { resetSubOrderForm(); dialogTitle.value = '小量新增'; assignReactive(subOrderForm, { ...createSubOrderForm(), ...buildDefaultsFromProject() }); dialogVisible.value = true }
watch(()=>subOrderForm.parentSubOrderId,()=>{
 if(subOrderForm.id||!dialogVisible.value)return
 const parent=subOrders.value.find(row=>row.id===subOrderForm.parentSubOrderId)||project
 for(const key of ['serviceContent','languagePair','customerDeadlineTime','customerRequirementProfessional','customerRequirementSpecial','remarks','fileTypeSecondary'])subOrderForm[key]=parent[key]||''
 subOrderForm.status=parent.status||parent.projectStatus||'pending_confirmation'
})
const openEditDialog = (row) => {
  resetSubOrderForm()
  dialogTitle.value = '编辑子订单'
  assignReactive(subOrderForm, {
    ...createSubOrderForm(), ...row,
    wordCountMatrix: displayedMatrices.value.get(row.id) ?? row.wordCountMatrix,
  })
  dialogVisible.value = true
}
const buildPayload = (source) => cleanPayload({ serviceContent:source.serviceContent||null, customerRequirementProfessional:source.customerRequirementProfessional||null, customerRequirementSpecial:source.customerRequirementSpecial||null, parentSubOrderId: source.parentSubOrderId || null, parentProjectId: projectId, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCountMatrix: source.wordCountMatrix, customerChargeItems: source.customerChargeItems || [], customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', translatorAssignmentTime: source.translatorAssignmentTime || '', status: normalizeStatus(source.status) || 'pending_confirmation', translatorDeliveryProgress: source.translatorDeliveryProgress || '', preReviewQcProgress: source.preReviewQcProgress || '', review1Progress: source.review1Progress || '', review2Progress: source.review2Progress || '', postReviewQcProgress: source.postReviewQcProgress || '', layoutProgress: source.layoutProgress || '', consolidationProgress: source.consolidationProgress || '', networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
const handleSubmit = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = projectFinanceFields(buildPayload(subOrderForm),!!subOrderForm.id); let saved; if (dialogTitle.value === '小量新增') { saved = await createSubOrder({...payload,preserveOriginalFile:true}); ElMessage.success('子订单创建成功') } else { saved = await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } if (saved?.autoCreatedChildCount) ElMessage.success(`已按翻译方向自动生成 ${saved.autoCreatedChildCount} 个子订单`); dialogVisible.value = false; await loadData();if(saved?.motherSplitReview?.required)editMother() } catch (error) {
        await subOrderFormRef.value?.applyServerErrors(error)
 ElMessage.error(getLocalizedErrorMessage(error, '保存失败')) } }
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({
  rows: subOrders,
  tableRef: subOrderTableRef,
  deleteRow: (row) => deleteSubOrder(row.id),
  getLabel: (row) => row.subOrderNo || row.subProjectName,
  reload: fetchSubOrders,
  entityName: '子订单',
})
const openBatchDialog = (mode='quantity') => { batchDialogMode.value=mode;batchDialogVisible.value = true }
const handleInlinePendingChange = (row, change) => {
  const next = new Map(inlineChanges.value)
  if (change.pending) next.set(String(change.id), { row, name: change.name, valid: change.valid })
  else next.delete(String(change.id))
  inlineChanges.value = next
}
const handleInlineSubOrderSaved = (row, updated) => {
  const next = new Map(inlineChanges.value)
  next.delete(String(updated.id))
  inlineChanges.value = next
  Object.assign(row, updated)
}
const saveSubOrderTranslatorCompletions = async (row, completions) => {
  const updated = await updateSubOrder(row.id, { assignedTranslatorCompletions: completions })
  handleInlineSubOrderSaved(row, updated)
  if (String(subOrderForm.id) === String(row.id)) assignReactive(subOrderForm, { ...createSubOrderForm(), ...updated })
  return updated
}
const saveAllInlineNames = async () => {
  const pending = [...inlineChanges.value.values()]
  if (!pending.length || inlineSaving.value) return
  if (pending.some((item) => !item.valid)) {
    ElMessage.warning('请先补全所有文件名称，再保存全部')
    return
  }
  if (inlineSaving.value) return
  inlineSaving.value = true
  try {
    const results = await Promise.allSettled(
      pending.map(async (item) => ({ item, updated: await updateSubOrder(item.row.id, { subProjectName: item.name }) }))
    )
    const remaining = new Map(inlineChanges.value)
    let successCount = 0
    results.forEach((result) => {
      if (result.status !== 'fulfilled') return
      successCount += 1
      remaining.delete(String(result.value.updated.id))
      Object.assign(result.value.item.row, result.value.updated)
    })
    inlineChanges.value = remaining
    const failedCount = results.length - successCount
    if (failedCount) ElMessage.warning(`已保存 ${successCount} 条，${failedCount} 条保存失败，请重试`)
    else ElMessage.success(`已保存 ${successCount} 条文件名称`)
  } finally {
    inlineSaving.value = false
  }
}
async function copyPath(path){try{await navigator.clipboard.writeText(path);ElMessage.success('路径已复制')}catch{ElMessage.info('可直接选中路径文字复制')}}
async function downloadHierarchy(){try{
 const data=await exportSubOrderTree(projectId)
 const url=URL.createObjectURL(data instanceof Blob?data:new Blob([data]))
 const link=document.createElement('a');link.href=url;link.download=(project.orderNo||'笔译')+'-订单层级与统计.xlsx';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}catch(error){ElMessage.error(getLocalizedErrorMessage(error,'导出失败'))}}
onMounted(loadData)
const customerFinanceEditorRef=ref(null)
</script>

<style scoped>
.suborder-management{height:calc(100dvh - 140px);min-height:280px;display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box}
.suborder-management--embedded{height:100%;min-height:0}
.suborder-management :deep(> .el-card__header){flex:none}
.suborder-management :deep(> .el-card__body){flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden;padding:8px 0 0}
.suborder-management > :deep(.el-card__body > .copyable-order-path){flex:none;margin:0 16px 8px;max-height:48px;overflow:auto}
.suborder-management :deep(.suborder-statistics-grid){height:100%;min-height:0;display:flex;flex-direction:column;padding:0 16px 8px;box-sizing:border-box;overflow:hidden}
.suborder-management :deep(.statistics-actions){flex:none;margin:0 0 8px}
.suborder-management :deep(.statistics-scroll){flex:1;min-height:0;max-height:none}
.suborder-list-region{height:100%;min-height:0;overflow:hidden}
.suborder-search{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:0 0 8px}
.suborder-search .el-input{width:min(360px,100%)}
.suborder-search .el-button+.el-button{margin-left:0}
.suborder-management-table{height:100%;border-radius:0!important}
.suborder-list-region :deep(.el-scrollbar__bar.is-horizontal){bottom:0;height:10px}
.suborder-list-region :deep(.el-scrollbar__bar.is-vertical){right:0;width:10px}

.copyable-order-path{user-select:text;white-space:pre-wrap;overflow-wrap:anywhere}
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-title { font-size: 18px; font-weight: 600; }
.page-subtitle { margin-top: 4px; color: #909399; }
.page-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.sub-order-name-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
.sub-order-name-header :deep(.el-button) { flex: none; padding: 0 2px; font-weight: 400; }
.sub-order-no-link { max-width: 100%; padding: 0; }
.word-count-summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }

:global(.suborder-editor-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  overflow: hidden;
}
:global(.suborder-editor-dialog .el-dialog__header),
:global(.suborder-editor-dialog .el-dialog__footer) {
  flex: none;
}
:global(.suborder-editor-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
:global(.suborder-editor-dialog .el-dialog__footer) {
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
  box-shadow: 0 -3px 10px rgba(0, 0, 0, 0.04);
}
</style>
