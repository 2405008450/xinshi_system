<template>
  <el-card>
    <template #header>
      <div class="page-header">
        <div>
          <div class="page-title">子订单管理</div>
          <div class="page-subtitle">{{ project.orderNo || route.query.orderNo || '-' }} / {{ project.projectName || route.query.projectName || '-' }}</div>
        </div>
        <div class="page-actions">
          <el-button @click="goBack">返回项目详情</el-button>
          <BatchDeleteToolbar
            v-if="canWriteProjects"
            :active="deleteMode"
            :selected-count="selectedRows.length"
            :loading="deleting"
            @enter="enterDeleteMode"
            @exit="exitDeleteMode"
            @confirm="confirmBatchDelete"
          />
          <el-button v-if="canWriteProjects && !deleteMode" type="primary" @click="openCreateDialog">新增子订单</el-button>
          <el-button v-if="canWriteProjects && !deleteMode" @click="openBatchDialog">批量新增子订单</el-button>
        </div>
      </div>
    </template>

    <el-table ref="subOrderTableRef" :data="subOrders" v-loading="loading" row-key="id" border @selection-change="handleDeleteSelectionChange">
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
            <span>子项目名称</span>
            <el-button
              v-if="canWriteProjects && !deleteMode"
              type="primary"
              link
              size="small"
              :icon="Check"
              :loading="inlineSaving"
              :disabled="inlinePendingCount === 0"
              title="保存全部子项目名称"
              @click="saveAllInlineNames"
            >保存全部{{ inlinePendingCount ? `（${inlinePendingCount}）` : '' }}</el-button>
          </div>
        </template>
        <template #default="{ row }">
          <InlineSubProjectName
            :sub-order-id="row.id"
            :model-value="row.subProjectName"
            :editable="canWriteProjects"
            @pending-change="handleInlinePendingChange(row, $event)"
            @saved="handleInlineSubOrderSaved(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="languagePair" label="翻译方向" min-width="120" />
      <el-table-column label="字数统计" min-width="220">
        <template #default="{ row }">
          <div class="word-count-summary">
            <span>{{ formatWordCountMatrix(row.wordCountMatrix) }}</span>
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

    <DraggableFormDialog
      v-model="dialogVisible"
      class="suborder-editor-dialog"
      :title="dialogTitle"
      width="min(900px, calc(100vw - 32px))"
      top="5vh"
      @closed="resetSubOrderForm"
    >
      <el-form ref="subOrderFormRef" :model="subOrderForm" :rules="subOrderRules" label-width="130px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="母订单号"><el-input :model-value="project.orderNo || route.query.orderNo" disabled /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="子订单号"><ReadonlyField :model-value="subOrderForm.subOrderNo" source="auto" placeholder="保存后自动生成" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="子项目名称" prop="subProjectName"><el-input v-model="subOrderForm.subProjectName" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="subOrderForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="文件二级类型"><el-input v-model="subOrderForm.fileTypeSecondary" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="subOrderForm.languagePair" :show-hint="false" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="优先级"><el-select v-model="subOrderForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="字数统计"><div class="word-count-summary"><span>{{ formatWordCountMatrix(subOrderForm.wordCountMatrix) }}</span><WordCountMatrixPopover v-model="subOrderForm.wordCountMatrix" entity-type="suborder" :entity-id="subOrderForm.id" title="子订单字数统计" @saved="fetchSubOrders" /></div></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="subOrderForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="subOrderForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="subOrderForm.translatorId" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员分配时间"><el-date-picker v-model="subOrderForm.translatorAssignmentTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
        </el-row>
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
          <el-col :span="8"><el-form-item label="网络文件路径"><el-input v-model="subOrderForm.networkFilePath" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="客户反馈"><el-input v-model="subOrderForm.clientFeedback" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="subOrderForm.remarks" type="textarea" :rows="3" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </DraggableFormDialog>

    <SubOrderBatchCreateDialog
      v-model="batchDialogVisible"
      :project="project"
      :existing-names="subOrders.map((item) => item.subProjectName).filter(Boolean)"
      @created="fetchSubOrders"
    />
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import { getProject } from '@/api/projects'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder } from '@/api/subOrders'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import InlineSubProjectName from './components/InlineSubProjectName.vue'
import SubOrderBatchCreateDialog from './components/SubOrderBatchCreateDialog.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { createEmptyWordCountMatrix, formatWordCountMatrix } from '@/utils/wordCountMatrix'
import { hasPermission } from '@/utils/permission'

const route = useRoute()
const router = useRouter()
const canWriteProjects = hasPermission('projects:write')
const projectId = route.params.projectId
const loading = ref(false)
const dialogVisible = ref(false)
const batchDialogVisible = ref(false)
const inlineChanges = ref(new Map())
const inlineSaving = ref(false)
const dialogTitle = ref('新增子订单')
const subOrderFormRef = ref(null)
const subOrderTableRef = ref(null)
const subOrders = ref([])
const inlinePendingCount = computed(() => inlineChanges.value.size)
const project = reactive({ id: '', orderNo: '', projectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), projectStatus: 'pending_confirmation', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorAssignmentTime: '', translatorDeliveryProgress: '', preReviewQcProgress: '', review1Progress: '', review2Progress: '', postReviewQcProgress: '', layoutProgress: '', consolidationProgress: '', networkFilePath: '' })
const createSubOrderForm = () => ({ id: '', parentProjectId: projectId, subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorAssignmentTime: '', status: 'pending_confirmation', translatorDeliveryProgress: '', preReviewQcProgress: '', review1Progress: '', review2Progress: '', postReviewQcProgress: '', layoutProgress: '', consolidationProgress: '', networkFilePath: '', remarks: '' })
const subOrderForm = reactive(createSubOrderForm())
const projectStatusOptions = [
  { label: '待确认', value: 'pending_confirmation' }, { label: '已确认', value: 'confirmed' },
  { label: '已整理', value: 'organized' }, { label: '已排译员', value: 'translator_assigned' },
  { label: '已发译员', value: 'sent_to_translator' }, { label: '译员发回', value: 'translator_returned' },
  { label: '已专检', value: 'special_checked' }, { label: '已排版', value: 'typeset' },
  { label: '已专检排版', value: 'special_checked_typeset' }, { label: '已审核', value: 'reviewed' },
  { label: '已发客户', value: 'sent_to_client' }, { label: '客户反馈', value: 'client_feedback' },
  { label: '反馈后发客户', value: 'feedback_sent_to_client' }, { label: '已取消', value: 'cancelled' },
  { label: '已部分取消', value: 'partially_cancelled' }, { label: '已暂停', value: 'paused' }
]
const priorityOptions = ['低', '中', '高', '紧急']
const subOrderRules = { subProjectName: [{ required: true, message: '请输入子项目名称', trigger: 'blur' }] }
const NULLABLE_FIELDS = ['subProjectName', 'fileTypeSecondary', 'languagePair', 'priority', 'customerDeadlineTime', 'sentToClientTime', 'clientFeedback', 'translatorId', 'translatorAssignmentTime', 'translatorDeliveryProgress', 'preReviewQcProgress', 'review1Progress', 'review2Progress', 'postReviewQcProgress', 'layoutProgress', 'consolidationProgress', 'networkFilePath', 'remarks']
const subOrderDetailItems = [
  { label: '子订单号', key: 'subOrderNo' }, { label: '子项目名称', key: 'subProjectName' },
  { label: '状态', key: 'status', type: 'status' }, { label: '文件二级类型', key: 'fileTypeSecondary' }, { label: '翻译方向', key: 'languagePair' }, { label: '优先级', key: 'priority' },
  { label: '字数统计', key: 'wordCountMatrix', formatter: formatWordCountMatrix }, { label: '客户交稿时间', key: 'customerDeadlineTime' }, { label: '发客户时间', key: 'sentToClientTime' }, { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' }, { label: '审校前QC', key: 'preReviewQcProgress' }, { label: '审校1', key: 'review1Progress' }, { label: '审校2', key: 'review2Progress' },
  { label: '审校后QC', key: 'postReviewQcProgress' }, { label: '排版进度', key: 'layoutProgress' }, { label: '整合进度', key: 'consolidationProgress' }, { label: '网络文件路径', key: 'networkFilePath', span: 2 },
  { label: '备注', key: 'remarks', span: 2 }, { label: '创建时间', key: 'createdAt' }, { label: '更新时间', key: 'updatedAt' }
]
const legacyStatusMap = { pending: 'pending_confirmation', in_progress: 'confirmed', completed: 'sent_to_client', terminated: 'cancelled' }
const normalizeStatus = (status) => legacyStatusMap[status] || status
const getStatusLabel = (status) => projectStatusOptions.find(item => item.value === normalizeStatus(status))?.label || status || '-'
const getStatusType = (status) => ({ pending_confirmation: 'info', confirmed: 'primary', organized: 'primary', translator_assigned: 'warning', sent_to_translator: 'warning', translator_returned: 'primary', special_checked: 'primary', typeset: 'primary', special_checked_typeset: 'primary', reviewed: 'success', sent_to_client: 'success', client_feedback: 'success', feedback_sent_to_client: 'success', cancelled: 'danger', partially_cancelled: 'danger', paused: 'warning' }[normalizeStatus(status)] || 'info')
const cloneValue = (value) => value && typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value
const assignReactive = (target, values) => { Object.keys(target).forEach((key) => { target[key] = cloneValue(values[key] ?? target[key]) }) }
const cleanPayload = (payload) => { const result = { ...payload }; NULLABLE_FIELDS.forEach((key) => { if (result[key] === '') result[key] = null }); return result }
const buildDefaultsFromProject = () => ({ fileTypeSecondary: project.fileTypeSecondary, languagePair: project.languagePair, priority: project.priority, wordCountMatrix: cloneValue(project.wordCountMatrix), customerDeadlineTime: project.customerDeadlineTime, sentToClientTime: project.sentToClientTime, clientFeedback: project.clientFeedback, translatorId: project.translatorId, translatorAssignmentTime: project.translatorAssignmentTime, status: normalizeStatus(project.projectStatus) || 'pending_confirmation', translatorDeliveryProgress: project.translatorDeliveryProgress, preReviewQcProgress: project.preReviewQcProgress, review1Progress: project.review1Progress, review2Progress: project.review2Progress, postReviewQcProgress: project.postReviewQcProgress, layoutProgress: project.layoutProgress, consolidationProgress: project.consolidationProgress, networkFilePath: project.networkFilePath })
const fetchProject = async () => { const response = await getProject(projectId); assignReactive(project, { ...project, ...response }) }
const fetchSubOrders = async () => { const response = await getSubOrdersByProject(projectId); subOrders.value = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []; inlineChanges.value = new Map() }
const loadData = async () => { loading.value = true; try { await Promise.all([fetchProject(), fetchSubOrders()]) } catch (error) { ElMessage.error(error.detail || error.message || '加载子订单失败') } finally { loading.value = false } }
const goBack = () => router.push({ name: 'TranslationProjectDetails' })
const resetSubOrderForm = () => { assignReactive(subOrderForm, createSubOrderForm()); subOrderFormRef.value?.clearValidate() }
const openCreateDialog = () => { resetSubOrderForm(); dialogTitle.value = '新增子订单'; assignReactive(subOrderForm, { ...createSubOrderForm(), ...buildDefaultsFromProject() }); dialogVisible.value = true }
const openEditDialog = (row) => { resetSubOrderForm(); dialogTitle.value = '编辑子订单'; assignReactive(subOrderForm, { ...createSubOrderForm(), ...row }); dialogVisible.value = true }
const buildPayload = (source) => cleanPayload({ parentProjectId: projectId, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCountMatrix: source.wordCountMatrix, customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', translatorAssignmentTime: source.translatorAssignmentTime || '', status: normalizeStatus(source.status) || 'pending_confirmation', translatorDeliveryProgress: source.translatorDeliveryProgress || '', preReviewQcProgress: source.preReviewQcProgress || '', review1Progress: source.review1Progress || '', review2Progress: source.review2Progress || '', postReviewQcProgress: source.postReviewQcProgress || '', layoutProgress: source.layoutProgress || '', consolidationProgress: source.consolidationProgress || '', networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
const handleSubmit = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = buildPayload(subOrderForm); if (dialogTitle.value === '新增子订单') { await createSubOrder(payload); ElMessage.success('子订单创建成功') } else { await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } dialogVisible.value = false; await loadData() } catch (error) { ElMessage.error(error.detail || error.message || '保存失败') } }
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({
  rows: subOrders,
  tableRef: subOrderTableRef,
  deleteRow: (row) => deleteSubOrder(row.id),
  getLabel: (row) => row.subOrderNo || row.subProjectName,
  reload: fetchSubOrders,
  entityName: '子订单',
})
const openBatchDialog = () => { batchDialogVisible.value = true }
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
const saveAllInlineNames = async () => {
  const pending = [...inlineChanges.value.values()]
  if (!pending.length || inlineSaving.value) return
  if (pending.some((item) => !item.valid)) {
    ElMessage.warning('请先补全所有子项目名称，再保存全部')
    return
  }
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
    else ElMessage.success(`已保存 ${successCount} 条子项目名称`)
  } finally {
    inlineSaving.value = false
  }
}
onMounted(loadData)
</script>

<style scoped>
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
