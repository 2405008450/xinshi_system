<template>
  <DraggableFormDialog
    :model-value="modelValue"
    class="suborder-batch-create-dialog"
    title="批量新增子订单"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
    @closed="reset"
  >
    <el-tabs v-model="mode">
      <el-tab-pane label="按数量生成" name="quantity">
        <AppForm label-position="top">
          <el-row :gutter="16">
            <el-col :xs="24" :md="12"><el-form-item label="生成数量"><el-input-number v-model="form.count" :min="1" :max="500" style="width:100%" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="起始序号"><el-input-number v-model="form.startIndex" :min="1" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="子项目名前缀"><el-input v-model="form.subProjectNamePrefix" maxlength="220" placeholder="留空则按 母项目名称-子订单01 自动生成" /></el-form-item>
          <el-alert type="info" :closable="false" show-icon :title="`将生成 ${quantityNames.length} 个子订单，名称示例：${quantityNames.slice(0, 3).join('、')}`" />
        </AppForm>
      </el-tab-pane>

      <el-tab-pane label="按文件名导入" name="filenames">
        <el-alert type="info" :closable="false" show-icon title="选择 TXT 后内容会填入文本框；也可以直接粘贴文件名，每行一个。确认预览后才会创建子订单。" />
        <el-upload
          v-model:file-list="fileList"
          class="filename-upload"
          :auto-upload="false"
          :limit="1"
          accept=".txt,text/plain"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-button>选择 TXT 文件</el-button>
          <template #tip><div class="el-upload__tip">支持 UTF-8、UTF-16LE、GBK，文件不超过 1MB。</div></template>
        </el-upload>
        <el-input
          v-model="filenameText"
          type="textarea"
          :rows="9"
          resize="vertical"
          placeholder="示例：&#10;合同正文.docx&#10;附件一.xlsx&#10;客户说明.pdf"
        />
        <div class="import-summary">
          <el-tag>共 {{ previewRows.length }} 条</el-tag>
          <el-tag type="success">将新增 {{ previewSummary.create }}</el-tag>
          <el-tag type="warning">重复 {{ previewSummary.duplicate }}</el-tag>
          <el-tag type="danger">错误 {{ previewSummary.error }}</el-tag>
          <span v-if="previewRows.length > 100">仅展示前 100 条，提交时处理全部有效内容。</span>
        </div>
        <el-table v-if="previewRows.length" :data="previewRows.slice(0, 100)" border size="small" max-height="320">
          <el-table-column prop="lineNumber" label="行号" width="72" />
          <el-table-column label="状态" width="92">
            <template #default="{ row }"><el-tag :type="previewTagType(row.status)" size="small">{{ previewStatusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="name" label="子项目名称" min-width="300" show-overflow-tooltip />
          <el-table-column prop="reason" label="说明" min-width="220"><template #default="{ row }">{{ row.reason || '-' }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-divider content-position="left">批量公共字段</el-divider>
    <AppForm label-position="top">
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="状态"><el-select v-model="form.status" clearable style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.priority" clearable style="width:100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="form.fileTypeSecondary" /></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="form.languagePair" :show-hint="false" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <el-form-item label="字数统计">
            <div class="word-count-summary"><span>{{ formatWordCountMatrix(form.wordCountMatrix) }}</span><WordCountMatrixPopover v-model="form.wordCountMatrix" title="批量子订单字数统计" /></div>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="form.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="form.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="译员 ID"><el-input v-model="form.translatorId" /></el-form-item></el-col>
      </el-row>
    </AppForm>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        {{ mode === 'filenames' ? `确认导入 ${previewSummary.create} 条` : `批量创建 ${quantityNames.length} 条` }}
      </el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createSubOrdersBulk } from '@/api/subOrders'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { createEmptyWordCountMatrix, formatWordCountMatrix } from '@/utils/wordCountMatrix'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  project: { type: Object, default: () => ({}) },
  existingNames: { type: Array, default: () => [] },
  initialMode: { type: String, default: 'quantity' },
})
const emit = defineEmits(['update:modelValue', 'created'])
const statusOptions = [
  ['待确认', 'pending_confirmation'], ['已确认', 'confirmed'], ['已整理', 'organized'],
  ['已排译员', 'translator_assigned'], ['已发译员', 'sent_to_translator'], ['译员发回', 'translator_returned'],
  ['已专检', 'special_checked'], ['已排版', 'typeset'], ['专检排版完成', 'special_checked_typeset'], ['已审核', 'reviewed'],
  ['已发客户', 'sent_to_client'], ['客户反馈', 'client_feedback'], ['反馈后发客户', 'feedback_sent_to_client'],
  ['已取消', 'cancelled'], ['部分取消', 'partially_cancelled'], ['已暂停', 'paused'],
].map(([label, value]) => ({ label, value }))
const priorityOptions = ['低', '中', '高', '紧急']
const mode = ref('quantity')
const filenameText = ref('')
const fileList = ref([])
const submitting = ref(false)

const clone = (value) => value && typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value
const createForm = () => ({
  count: 1,
  startIndex: 1,
  subProjectNamePrefix: props.project.projectName ? `${props.project.projectName}-子订单` : '',
  fileTypeSecondary: props.project.fileTypeSecondary || '',
  languagePair: props.project.languagePair || '',
  priority: props.project.priority || '',
  wordCountMatrix: clone(props.project.wordCountMatrix) || createEmptyWordCountMatrix(),
  customerDeadlineTime: props.project.customerDeadlineTime || '',
  sentToClientTime: props.project.sentToClientTime || '',
  clientFeedback: props.project.clientFeedback || '',
  translatorId: props.project.translatorId || '',
  translatorAssignmentTime: props.project.translatorAssignmentTime || '',
  status: props.project.projectStatus || props.project.status || 'pending_confirmation',
  translatorDeliveryProgress: props.project.translatorDeliveryProgress || '',
  preReviewQcProgress: props.project.preReviewQcProgress || '',
  reviewProgress: props.project.reviewProgress || '',
  review1Progress: props.project.review1Progress || '',
  review2Progress: props.project.review2Progress || '',
  postReviewQcProgress: props.project.postReviewQcProgress || '',
  layoutProgress: props.project.layoutProgress || '',
  consolidationProgress: props.project.consolidationProgress || '',
  networkFilePath: props.project.networkFilePath || '',
  remarks: '',
})
const form = reactive(createForm())
const normalizeName = (value) => String(value || '').trim().toLocaleLowerCase()

const quantityNames = computed(() => {
  const prefix = form.subProjectNamePrefix.trim() || (props.project.projectName ? `${props.project.projectName}-子订单` : '子订单')
  return Array.from({ length: Number(form.count) || 0 }, (_, offset) => `${prefix}${String(Number(form.startIndex) + offset).padStart(2, '0')}`)
})

const previewRows = computed(() => {
  const existing = new Set(props.existingNames.map(normalizeName).filter(Boolean))
  const seen = new Set()
  let contentIndex = 0
  return filenameText.value.split(/\r\n|\n|\r/).reduce((rows, rawName, index) => {
    const name = String(rawName || '').replace(/^\ufeff/, '').trim()
    if (!name) return rows
    contentIndex += 1
    const key = normalizeName(name)
    let status = 'create'
    let reason = ''
    if (contentIndex > 500) {
      status = 'error'; reason = '单次最多导入 500 条'
    } else if (name.length > 255) {
      status = 'error'; reason = '名称不能超过 255 个字符'
    } else if (existing.has(key)) {
      status = 'duplicate'; reason = '当前母订单已存在同名子订单'
    } else if (seen.has(key)) {
      status = 'duplicate'; reason = '本次导入内容中名称重复'
    }
    if (status === 'create') seen.add(key)
    rows.push({ lineNumber: index + 1, name, status, reason })
    return rows
  }, [])
})
const previewSummary = computed(() => previewRows.value.reduce((summary, row) => {
  summary[row.status] += 1
  return summary
}, { create: 0, duplicate: 0, error: 0 }))
const canSubmit = computed(() => {
  if (!props.project.id || submitting.value) return false
  if (mode.value === 'quantity') return quantityNames.value.length > 0 && quantityNames.value.every((name) => name.length <= 255)
  return previewSummary.value.create > 0 && previewSummary.value.error === 0
})

const decodeTextFile = async (file) => {
  if (!file.name.toLocaleLowerCase().endsWith('.txt')) throw new Error('请选择 TXT 文件')
  if (file.size > 1024 * 1024) throw new Error('TXT 文件不能超过 1MB')
  const buffer = await file.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return new TextDecoder('utf-16le').decode(bytes.subarray(2))
  if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) return new TextDecoder('utf-8').decode(bytes.subarray(3))
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return new TextDecoder('gbk').decode(bytes)
  }
}
const handleFileChange = async (uploadFile) => {
  try {
    filenameText.value = await decodeTextFile(uploadFile.raw)
  } catch (error) {
    fileList.value = []
    ElMessage.error('读取 TXT 文件失败，请确认文件内容和编码格式')
  }
}
const handleFileRemove = () => { fileList.value = [] }
const previewTagType = (status) => ({ create: 'success', duplicate: 'warning', error: 'danger' }[status] || 'info')
const previewStatusLabel = (status) => ({ create: '新增', duplicate: '跳过', error: '错误' }[status] || status)
const progressValue = (value) => value === '' || value === null || value === undefined ? null : String(value)

const buildDefaults = () => ({
  fileTypeSecondary: form.fileTypeSecondary || null,
  languagePair: form.languagePair || null,
  priority: form.priority || null,
  wordCountMatrix: form.wordCountMatrix,
  customerDeadlineTime: form.customerDeadlineTime || null,
  sentToClientTime: form.sentToClientTime || null,
  clientFeedback: form.clientFeedback || null,
  translatorId: form.translatorId || null,
  translatorAssignmentTime: form.translatorAssignmentTime || null,
  status: form.status || 'pending_confirmation',
  translatorDeliveryProgress: progressValue(form.translatorDeliveryProgress),
  preReviewQcProgress: progressValue(form.preReviewQcProgress),
  reviewProgress: progressValue(form.reviewProgress),
  review1Progress: progressValue(form.review1Progress),
  review2Progress: progressValue(form.review2Progress),
  postReviewQcProgress: progressValue(form.postReviewQcProgress),
  layoutProgress: progressValue(form.layoutProgress),
  consolidationProgress: progressValue(form.consolidationProgress),
  networkFilePath: form.networkFilePath || null,
  remarks: form.remarks || null,
})
const submit = async () => {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const names = mode.value === 'quantity'
      ? quantityNames.value
      : previewRows.value.filter((row) => row.status !== 'error').map((row) => row.name)
    const result = await createSubOrdersBulk({ parentProjectId: props.project.id, subProjectNames: names, defaults: buildDefaults() })
    ElMessage.success(`批量创建完成：新增 ${result.createdCount} 条，跳过 ${result.skippedCount} 条`)
    if (result.skippedCount) {
      const reasons = result.skipped.slice(0, 3).map((item) => `${item.name}：${item.reason}`).join('；')
      ElMessage.warning(`已跳过重复名称：${reasons}${result.skippedCount > 3 ? '；更多结果未展开' : ''}`)
    }
    emit('created', result)
    emit('update:modelValue', false)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '批量创建子订单失败'))
  } finally {
    submitting.value = false
  }
}
const reset = () => {
  mode.value = props.initialMode === 'filenames' ? 'filenames' : 'quantity'
  filenameText.value = ''
  fileList.value = []
  Object.assign(form, createForm())
}
watch(() => props.modelValue, (visible) => { if (visible) reset() })
</script>

<style scoped>
.filename-upload { margin: 14px 0; }
.import-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 14px 0 10px; }
.import-summary span { color: var(--el-text-color-secondary); font-size: 12px; }
.word-count-summary { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 32px; gap: 8px; padding: 0 10px; border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-fill-color-lighter); }
</style>

<style>
.suborder-batch-create-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.suborder-batch-create-dialog .el-dialog__header,
.suborder-batch-create-dialog .el-dialog__footer { flex: 0 0 auto; }
.suborder-batch-create-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.suborder-batch-create-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); box-shadow: 0 -3px 10px rgb(0 0 0 / 4%); }
</style>
