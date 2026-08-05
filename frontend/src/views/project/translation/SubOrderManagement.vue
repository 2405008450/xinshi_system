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
          <el-button type="primary" @click="openCreateDialog">新增子订单</el-button>
          <el-button @click="openBatchDialog">批量新增子订单</el-button>
        </div>
      </div>
    </template>

    <el-table :data="subOrders" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="subOrderNo" label="子订单号" min-width="180" />
      <el-table-column prop="subProjectName" label="子项目名称" min-width="200" show-overflow-tooltip />
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
      <el-table-column label="详情" width="100">
        <template #default="{ row }">
          <DetailPopover :row="row" title="子订单详情" :items="subOrderDetailItems" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton action="edit" @click="openEditDialog(row)" />
          <TableActionButton action="delete" @click="handleDelete(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" @closed="resetSubOrderForm">
      <el-form ref="subOrderFormRef" :model="subOrderForm" :rules="subOrderRules" label-width="130px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="母订单号"><el-input :model-value="project.orderNo || route.query.orderNo" disabled /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="子订单号"><el-input v-model="subOrderForm.subOrderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
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
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="subOrderForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="subOrderForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="subOrderForm.translatorId" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员分配时间"><el-date-picker v-model="subOrderForm.translatorAssignmentTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
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
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="批量新增子订单" width="860px" @closed="resetBatchForm">
      <el-form ref="batchFormRef" :model="batchForm" :rules="batchRules" label-width="140px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="生成数量" prop="count"><el-input-number v-model="batchForm.count" :min="1" :max="100" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="起始序号"><el-input-number v-model="batchForm.startIndex" :min="1" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="子项目名前缀"><el-input v-model="batchForm.subProjectNamePrefix" placeholder="留空则按 母项目名称-子订单01 自动生成" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">批量公共字段</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="batchForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="优先级"><el-select v-model="batchForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="文件二级类型"><el-input v-model="batchForm.fileTypeSecondary" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="batchForm.languagePair" :show-hint="false" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="字数统计"><div class="word-count-summary"><span>{{ formatWordCountMatrix(batchForm.wordCountMatrix) }}</span><WordCountMatrixPopover v-model="batchForm.wordCountMatrix" title="批量子订单字数统计" /></div></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="batchForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="batchForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="batchForm.translatorId" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchCreate">批量创建</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElDescriptions, ElDescriptionsItem, ElMessage, ElMessageBox, ElPopover, ElTag } from 'element-plus'
import { getProject } from '@/api/projects'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder } from '@/api/subOrders'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import { createEmptyWordCountMatrix, formatWordCountMatrix } from '@/utils/wordCountMatrix'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId
const loading = ref(false)
const dialogVisible = ref(false)
const batchDialogVisible = ref(false)
const dialogTitle = ref('新增子订单')
const subOrderFormRef = ref(null)
const batchFormRef = ref(null)
const subOrders = ref([])
const project = reactive({ id: '', orderNo: '', projectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), projectStatus: 'pending', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorAssignmentTime: '', translatorDeliveryProgress: '', preReviewQcProgress: '', review1Progress: '', review2Progress: '', postReviewQcProgress: '', layoutProgress: '', consolidationProgress: '', networkFilePath: '' })
const createSubOrderForm = () => ({ id: '', parentProjectId: projectId, subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorAssignmentTime: '', status: 'pending', translatorDeliveryProgress: '', preReviewQcProgress: '', review1Progress: '', review2Progress: '', postReviewQcProgress: '', layoutProgress: '', consolidationProgress: '', networkFilePath: '', remarks: '' })
const createBatchForm = () => ({ count: 1, startIndex: 1, subProjectNamePrefix: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), customerDeadlineTime: '', sentToClientTime: '', translatorId: '', status: 'pending' })
const subOrderForm = reactive(createSubOrderForm())
const batchForm = reactive(createBatchForm())
const projectStatusOptions = [{ label: '待启动', value: 'pending' }, { label: '进行中', value: 'in_progress' }, { label: '已完成', value: 'completed' }, { label: '已暂停', value: 'paused' }, { label: '已终止', value: 'terminated' }]
const priorityOptions = ['低', '中', '高', '紧急']
const subOrderRules = { subProjectName: [{ required: true, message: '请输入子项目名称', trigger: 'blur' }] }
const batchRules = { count: [{ required: true, message: '请输入生成数量', trigger: 'change' }] }
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
const getStatusLabel = (status) => projectStatusOptions.find(item => item.value === status)?.label || status || '-'
const getStatusType = (status) => ({ pending: 'info', in_progress: 'warning', completed: 'success', paused: 'danger', terminated: 'info' }[status] || 'info')
const displayValue = (value) => (value === null || value === undefined || value === '' ? '-' : value)
const cloneValue = (value) => value && typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value
const assignReactive = (target, values) => { Object.keys(target).forEach((key) => { target[key] = cloneValue(values[key] ?? target[key]) }) }
const cleanPayload = (payload) => { const result = { ...payload }; NULLABLE_FIELDS.forEach((key) => { if (result[key] === '') result[key] = null }); return result }
const buildDefaultsFromProject = () => ({ fileTypeSecondary: project.fileTypeSecondary, languagePair: project.languagePair, priority: project.priority, wordCountMatrix: cloneValue(project.wordCountMatrix), customerDeadlineTime: project.customerDeadlineTime, sentToClientTime: project.sentToClientTime, clientFeedback: project.clientFeedback, translatorId: project.translatorId, translatorAssignmentTime: project.translatorAssignmentTime, status: project.projectStatus || 'pending', translatorDeliveryProgress: project.translatorDeliveryProgress, preReviewQcProgress: project.preReviewQcProgress, review1Progress: project.review1Progress, review2Progress: project.review2Progress, postReviewQcProgress: project.postReviewQcProgress, layoutProgress: project.layoutProgress, consolidationProgress: project.consolidationProgress, networkFilePath: project.networkFilePath })
const fetchProject = async () => { const response = await getProject(projectId); assignReactive(project, { ...project, ...response }) }
const fetchSubOrders = async () => { const response = await getSubOrdersByProject(projectId); subOrders.value = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : [] }
const loadData = async () => { loading.value = true; try { await Promise.all([fetchProject(), fetchSubOrders()]) } catch (error) { ElMessage.error(error.detail || error.message || '加载子订单失败') } finally { loading.value = false } }
const goBack = () => router.push({ name: 'TranslationProjectDetails' })
const resetSubOrderForm = () => { assignReactive(subOrderForm, createSubOrderForm()); subOrderFormRef.value?.clearValidate() }
const resetBatchForm = () => { assignReactive(batchForm, createBatchForm()); batchFormRef.value?.clearValidate() }
const openCreateDialog = () => { resetSubOrderForm(); dialogTitle.value = '新增子订单'; assignReactive(subOrderForm, { ...createSubOrderForm(), ...buildDefaultsFromProject() }); dialogVisible.value = true }
const openEditDialog = (row) => { resetSubOrderForm(); dialogTitle.value = '编辑子订单'; assignReactive(subOrderForm, { ...createSubOrderForm(), ...row }); dialogVisible.value = true }
const buildPayload = (source) => cleanPayload({ parentProjectId: projectId, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCountMatrix: source.wordCountMatrix, customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', translatorAssignmentTime: source.translatorAssignmentTime || '', status: source.status || 'pending', translatorDeliveryProgress: source.translatorDeliveryProgress || '', preReviewQcProgress: source.preReviewQcProgress || '', review1Progress: source.review1Progress || '', review2Progress: source.review2Progress || '', postReviewQcProgress: source.postReviewQcProgress || '', layoutProgress: source.layoutProgress || '', consolidationProgress: source.consolidationProgress || '', networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
const handleSubmit = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = buildPayload(subOrderForm); if (dialogTitle.value === '新增子订单') { await createSubOrder(payload); ElMessage.success('子订单创建成功') } else { await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } dialogVisible.value = false; await loadData() } catch (error) { ElMessage.error(error.detail || error.message || '保存失败') } }
const handleDelete = async (row) => { try { await ElMessageBox.confirm(`确认删除子订单 ${row.subOrderNo} 吗？`, '提示', { type: 'warning' }); await deleteSubOrder(row.id); ElMessage.success('删除成功'); await fetchSubOrders() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || error.message || '删除失败') } }
const openBatchDialog = () => { resetBatchForm(); assignReactive(batchForm, { ...createBatchForm(), ...buildDefaultsFromProject(), subProjectNamePrefix: project.projectName ? `${project.projectName}-子订单` : '' }); batchDialogVisible.value = true }
const createBatchSubProjectName = (index) => { const prefix = batchForm.subProjectNamePrefix || (project.projectName ? `${project.projectName}-子订单` : '子订单'); return `${prefix}${String(index).padStart(2, '0')}` }
const handleBatchCreate = async () => { if (!batchFormRef.value) return; const valid = await batchFormRef.value.validate().catch(() => false); if (!valid) return; try { for (let offset = 0; offset < batchForm.count; offset += 1) { const sequence = batchForm.startIndex + offset; await createSubOrder(buildPayload({ ...batchForm, subProjectName: createBatchSubProjectName(sequence), remarks: '' })) } batchDialogVisible.value = false; ElMessage.success(`已批量创建 ${batchForm.count} 条子订单`); await fetchSubOrders() } catch (error) { ElMessage.error(error.detail || error.message || '批量新增失败') } }
const DetailPopover = defineComponent({ name: 'DetailPopover', props: { row: { type: Object, required: true }, title: { type: String, default: '详情' }, items: { type: Array, default: () => [] } }, setup(props) { return () => h(ElPopover, { placement: 'left', width: 720, trigger: 'click', title: props.title }, { reference: () => h(ElButton, { type: 'info', size: 'small', link: true }, () => '查看详情'), default: () => h('div', { class: 'detail-popover' }, h(ElDescriptions, { column: 2, border: true }, () => props.items.map((item) => h(ElDescriptionsItem, { key: item.key, label: item.label, span: item.span || 1 }, () => item.type === 'status' ? h(ElTag, { type: getStatusType(props.row[item.key]) }, () => getStatusLabel(props.row[item.key])) : h('span', { class: 'detail-value' }, displayValue(item.formatter ? item.formatter(props.row[item.key], props.row) : props.row[item.key])))))) }) } })
onMounted(loadData)
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-title { font-size: 18px; font-weight: 600; }
.page-subtitle { margin-top: 4px; color: #909399; }
.page-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.detail-popover { max-height: 620px; overflow-y: auto; }
.detail-value { color: #606266; word-break: break-all; }
.word-count-summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
</style>
