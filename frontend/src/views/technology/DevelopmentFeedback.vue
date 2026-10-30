<template>
  <el-card class="common-page-card development-feedback" v-loading="loading" shadow="never">
    <template #header><div class="feedback-header"><h2>开发反馈</h2><div><TableColumnSettings v-model="selectedKeys" :columns="columns" settings-key="development-feedback" @reset="resetColumns" /><el-button @click="load">刷新</el-button></div></div></template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!enabled && !loading" title="开发反馈数据表尚未初始化" type="warning" :closable="false" />
    <div class="feedback-filters"><el-input v-model="keyword" clearable placeholder="任务、反馈编号、功能模块、反馈内容、人员、意见" aria-label="搜索开发反馈" @keyup.enter="search" /><el-button @click="search">查询</el-button><el-button @click="keyword = ''; search()">重置</el-button></div>
    <p class="feedback-help">直接编辑单元格，离开输入框或选择选项后保存；多行文字可按 Ctrl+Enter 保存。意见保留填写账号、时间及修改记录。</p>
    <el-empty v-if="!groups.length && !loading" description="暂无开发反馈表，请从技术开发任务右侧生成" />
    <el-collapse v-model="expanded">
      <el-collapse-item v-for="group in visibleGroups" :key="group.task_id" :name="group.task_id">
        <template #title><strong>（开发）{{ group.task_name }}</strong><el-tag size="small" type="info">{{ group.task_no }}</el-tag><span>{{ group.items.length }} 条反馈</span></template>
        <div class="feedback-group-actions"><el-button type="primary" :loading="creating === group.task_id" :disabled="!!creating" @click="create(group)">新增反馈</el-button></div>
        <el-table :data="group.items" row-key="id" border class="feedback-editable-table">
          <el-table-column v-if="isVisible('feedback_no')" prop="feedback_no" label="反馈编号" width="175"><template #default="{ row }"><ReadonlyField :model-value="row.feedback_no" source="auto" /></template></el-table-column>
          <el-table-column v-if="isVisible('submitted_on')" label="提交日期" width="150"><template #default="{ row }"><ReadonlyField :model-value="row.submitted_on" source="auto" /></template></el-table-column>
          <el-table-column v-if="isVisible('reporter')" label="反馈人" width="180"><template #default="{ row }"><ReadonlyField :model-value="`${row.submitted_name}（${row.submitted_username}）`" source="auto" /></template></el-table-column>
          <el-table-column v-for="column in editableColumns" :key="column.key" :label="column.label" :min-width="column.width">
            <template #default="{ row }">
              <template v-if="column.opinion">
                <FeedbackEditableCell :model-value="latest(row, column.opinion)?.content || ''" :label="`${row.feedback_no} ${column.label}`" :editable="access[column.opinion]" :save-value="value => saveOpinion(row, column.opinion, value)" />
                <small v-if="latest(row, column.opinion)" class="opinion-author">{{ latest(row, column.opinion).author_name }}（{{ latest(row, column.opinion).author_username }}） · {{ formatTime(latest(row, column.opinion).created_at) }}</small>
                <el-popover trigger="click" placement="left" :width="520" :title="`${column.label}记录`"><div class="opinion-history"><article v-for="entry in opinionHistory(row, column.opinion)" :key="entry.id"><strong>{{ entry.author_name }}（{{ entry.author_username }}）</strong><small>{{ formatTime(entry.created_at) }}</small><p>{{ entry.content }}</p></article><el-empty v-if="!opinionHistory(row, column.opinion).length" description="暂无意见" :image-size="50" /></div><template #reference><el-button link type="primary">意见记录（{{ opinionHistory(row, column.opinion).length }}）</el-button></template></el-popover>
              </template>
              <FeedbackEditableCell v-else :model-value="row[column.key]" :type="column.type || 'textarea'" :label="`${row.feedback_no} ${column.label}`" :editable="row.can_edit" :options="optionsFor(column.key)" :clearable="column.key === 'assignee_id'" :current-label="column.key === 'assignee_id' ? row.assignee_name : ''" :save-value="value => saveCell(row, column.key, value)" />
            </template>
          </el-table-column>
          <el-table-column label="详情" width="100" fixed="right"><template #default="{ row }"><el-popover trigger="click" placement="left" :width="760" title="开发反馈详情"><div class="feedback-details"><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="field in columns" :key="field.key" :label="field.label"><ScreenshotText v-if="field.key === 'attachments'" :text="row.attachments || '-'" /><span v-else>{{ detailValue(row, field) }}</span></el-descriptions-item></el-descriptions></div><template #reference><el-button link type="primary">查看详情</el-button></template></el-popover></template></el-table-column>
        </el-table>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import FeedbackEditableCell from './FeedbackEditableCell.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { matchesSearchFields } from '@/utils/searchMatching'
import { formatBusinessDateTimeMinute as formatTime } from '@/utils/datetime'
import * as api from '@/api/developmentFeedback'
const route = useRoute(), groups = ref([]), expanded = ref([]), loading = ref(false), error = ref(''), enabled = ref(true), creating = ref(''), keyword = ref(''), appliedKeyword = ref(''), assignees = ref([])
const access = reactive({ william: false, development: false })
const columns = [
  { key: 'feedback_no', label: '反馈编号' }, { key: 'submitted_on', label: '提交日期' }, { key: 'reporter', label: '反馈人' },
  { key: 'module', label: '涉及功能模块', type: 'text', width: 180 }, { key: 'content', label: '反馈内容', width: 280 }, { key: 'urgency', label: '紧急程度', type: 'select', width: 120 }, { key: 'attachments', label: '附件或截图链接', type: 'attachments', width: 290 },
  { key: 'william', label: 'William意见', opinion: 'william', width: 270 }, { key: 'development', label: '开发部门意见', opinion: 'development', width: 270 },
  { key: 'status', label: '处理状态', type: 'select', width: 145 }, { key: 'assignee_id', label: '负责人', type: 'select', width: 160 }, { key: 'result', label: '处理结果', width: 240 }, { key: 'completed_on', label: '完成日期', type: 'date', width: 170 }, { key: 'notes', label: '备注', width: 220 }
]
const { selectedKeys, isVisible, reset: resetColumns } = useTableColumns('development-feedback', columns, columns.map(column => column.key))
const editableColumns = computed(() => columns.filter(column => column.width && isVisible(column.key)))
const opinionHistory = (row, kind) => row.opinions.filter(opinion => opinion.kind === kind)
const latest = (row, kind) => opinionHistory(row, kind)[0]
const optionsFor = key => key === 'urgency' ? ['低', '中', '高', '紧急'].map(value => ({ value, label: value })) : key === 'status' ? ['待处理', '处理中', '已解决', '暂不处理'].map(value => ({ value, label: value })) : key === 'assignee_id' ? assignees.value.map(person => ({ value: person.id, label: person.name })) : []
const visibleGroups = computed(() => groups.value.flatMap(group => {
  if (!appliedKeyword.value || matchesSearchFields([group.task_name, group.task_no], appliedKeyword.value)) return [group]
  const items = group.items.filter(row => matchesSearchFields([row.feedback_no, row.module, row.content, row.submitted_name, row.submitted_username, row.urgency, row.status, row.assignee_name, row.result, row.notes, ...row.opinions.map(opinion => `${opinion.content} ${opinion.author_name} ${opinion.author_username}`)], appliedKeyword.value))
  return items.length ? [{ ...group, items }] : []
}))
let controller, sequence = 0, timer, alive = true
const queues = new Map(), requestIds = new Map()
function search() { clearTimeout(timer); appliedKeyword.value = keyword.value; if (keyword.value) expanded.value = visibleGroups.value.map(group => group.task_id) }
watch(keyword, value => { clearTimeout(timer); if (!value) search(); else timer = setTimeout(search, 400) })
function revealTask() { if (route.query.taskId) expanded.value = [...new Set([...expanded.value, String(route.query.taskId)])] }
watch(() => route.query.taskId, revealTask)
async function load() {
  if (queues.size) { ElMessage.info('请等待当前单元格保存完成后刷新'); return }
  const current = ++sequence; controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { const value = await api.getDevelopmentFeedback(controller.signal); if (alive && current === sequence) { groups.value = value.groups; enabled.value = value.enabled; Object.assign(access, value.access); assignees.value = value.assignees; revealTask() } }
  catch (e) { if (alive && current === sequence && e.code !== 'ERR_CANCELED') error.value = typeof e.detail === 'string' ? e.detail : '加载开发反馈失败' }
  finally { if (alive && current === sequence) loading.value = false }
}
async function create(group) {
  if (creating.value) return
  creating.value = group.task_id
  if (!requestIds.has(group.task_id)) requestIds.set(group.task_id, crypto.randomUUID())
  try { const row = await api.createFeedbackRow(group.task_id, requestIds.get(group.task_id)); if (!group.items.some(item => item.id === row.id)) group.items.push(row); requestIds.delete(group.task_id); ElMessage.success('已新增反馈，可直接填写表格') }
  catch (e) { ElMessage.error(typeof e.detail === 'string' ? e.detail : '新增失败，请重试') }
  finally { creating.value = '' }
}
function enqueue(row, operation) {
  const previous = queues.get(row.id) || Promise.resolve()
  const next = previous.catch(() => {}).then(operation)
  queues.set(row.id, next)
  return next.finally(() => { if (queues.get(row.id) === next) queues.delete(row.id) })
}
function saveCell(row, key, value) {
  return enqueue(row, async () => { const result = await api.updateFeedbackRow(row.id, { revision: row.revision, [key]: ['assignee_id', 'completed_on'].includes(key) ? value || null : value }); Object.assign(row, result) })
}
function saveOpinion(row, kind, value) {
  return enqueue(row, async () => { const result = await api.addFeedbackOpinion(row.id, { kind, content: value, expected_latest_id: latest(row, kind)?.id || null }); Object.assign(row, result) })
}
function detailValue(row, field) {
  if (field.key === 'reporter') return `${row.submitted_name}（${row.submitted_username}）`
  if (field.opinion) { const value = latest(row, field.opinion); return value ? `${value.content}\n${value.author_name}（${value.author_username}） · ${formatTime(value.created_at)}` : '-' }
  if (field.key === 'assignee_id') return row.assignee_name || '-'
  return row[field.key] || '-'
}
onMounted(load); onBeforeUnmount(() => { alive = false; sequence++; controller?.abort(); clearTimeout(timer) })
</script>
<style scoped>
.feedback-header,.feedback-header>div,.feedback-filters,.feedback-group-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.feedback-header{justify-content:space-between}.feedback-header h2{margin:0;font-size:18px}.feedback-filters{margin:14px 0}.feedback-filters>.el-input{width:460px;max-width:100%}.feedback-help,.opinion-author{font-size:12px;color:var(--el-text-color-secondary)}.feedback-group-actions{margin:8px 0 12px}.development-feedback :deep(.el-collapse-item__title){display:flex;align-items:center;gap:10px;min-width:0}.feedback-details{max-height:560px;overflow-y:auto;white-space:pre-wrap;overflow-wrap:anywhere}.opinion-author{display:block;white-space:normal}.opinion-history{max-height:480px;overflow-y:auto;white-space:pre-wrap;overflow-wrap:anywhere}.opinion-history article{padding:12px 0;border-bottom:1px solid var(--el-border-color)}.opinion-history small{display:block;color:var(--el-text-color-secondary)}
</style>
