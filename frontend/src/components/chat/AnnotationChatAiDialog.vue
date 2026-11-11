<template>
  <DraggableFormDialog v-model="visible" :title="mode === 'run' ? '运行 AI 分析' : 'AI 分析结果'"
    width="min(820px, calc(100vw - 32px))" top="5vh" append-to-body class="annotation-chat-ai-dialog"
    @closed="emit('close')">
    <template v-if="mode === 'run'">
      <div class="chat-ai-fields">
        <div>
          <strong>会话范围</strong>
          <el-radio-group v-model="scope" aria-label="会话范围">
            <el-radio value="current">当前会话</el-radio>
            <el-radio value="all">我参与的全部标注会话</el-radio>
          </el-radio-group>
        </div>
        <div>
          <strong>时间范围</strong>
          <el-radio-group v-model="period" aria-label="时间范围">
            <el-radio v-for="option in periods" :key="option.value" :value="option.value">{{ option.label }}</el-radio>
          </el-radio-group>
        </div>
        <p class="chat-ai-muted">{{ periods.find(option => option.value === period)?.hint }}</p>
      </div>
    </template>
    <template v-else>
      <div class="chat-ai-history">
        <el-select v-model="selected" aria-label="分析批次" placeholder="选择分析批次" :loading="loading" @change="loadDetail">
          <el-option v-for="row in runs" :key="row.id" :label="runLabel(row)" :value="row.id" />
        </el-select>
        <el-button :loading="loading" @click="refresh">刷新</el-button>
        <el-button v-if="hasMore" :loading="loading" @click="loadOlder">加载更早批次</el-button>
      </div>
      <el-empty v-if="!loading && !runs.length && !error" description="暂无分析记录" :image-size="60" />
      <template v-if="run">
        <el-descriptions :column="1" size="small" border class="chat-ai-range">
          <el-descriptions-item label="聊天范围">{{ run.rangeStart ? formatBusinessDateTime(run.rangeStart) : '最早一条' }} 至 {{ formatBusinessDateTime(run.rangeEnd) }}</el-descriptions-item>
          <el-descriptions-item label="运行状态">{{ stateLabels[run.state] }}{{ run.autoApply ? ' · 分析后加入进度' : '' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="run.error || run.importError" :title="run.error || run.importError" type="error" :closable="false" />
        <template v-if="run.state === 'succeeded'">
          <el-empty v-if="!run.results.length" description="此时段没有可分类的聊天要点" :image-size="60" />
          <section v-for="group in groupedResults" :key="group.key" class="chat-ai-group">
            <h3>{{ group.label }}（{{ group.items.length }}）</h3>
            <ul>
              <li v-for="item in group.items" :key="item.id">
                <div class="chat-ai-summary">{{ item.summary }}</div>
                <small class="chat-ai-muted">{{ formatBusinessDateTime(item.effectiveAt) }} · {{ item.sources.length }} 条来源消息<span v-if="importedIds.has(item.id)"> · 已加入项目进度</span></small>
              </li>
            </ul>
          </section>
          <section v-if="run.imports.length" class="chat-ai-group">
            <h3>AI 操作记录</h3>
            <ul>
              <li v-for="entry in run.imports" :key="entry.resultId">
                {{ formatBusinessDateTime(entry.at) }} · {{ entry.actorName }}触发 AI {{ entry.operation === 'ai_progress_reused' ? '关联已有记录' : '加入项目进度' }} · {{ categories[entry.track] }}
              </li>
            </ul>
          </section>
        </template>
      </template>
    </template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <template v-if="mode === 'run'">
        <el-button :disabled="submitting" @click="showHistory">查看分析结果</el-button>
        <el-button type="primary" :loading="submitting && !applying" :disabled="submitting" @click="submit(false)">仅分析</el-button>
        <el-button v-if="canWrite" type="primary" :loading="submitting && applying" :disabled="submitting" @click="submit(true)">分析并加入进度</el-button>
      </template>
      <el-button v-else-if="canWrite" type="primary" :disabled="!canImport" :loading="submitting" @click="addProgress">加入项目进度</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { chatRequest } from '@/api/projectChat'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { hasPermission } from '@/utils/permission'

const props = defineProps({ projectId: { type: String, required: true }, initialMode: { type: String, required: true } })
const emit = defineEmits(['close'])
const periods = [
  { value: 'day', label: '前一天', hint: '从昨天零点到本次运行时刻。' },
  { value: 'week', label: '前一周', hint: '从七天前的同一时刻到本次运行时刻。' },
  { value: 'month', label: '前一个月', hint: '从上个月的对应日期和时刻到本次运行时刻。' },
  { value: 'all', label: '全部', hint: '分析此会话的全部可用文字，较长的记录会分批处理。' },
]
const categories = {
  customer: '项目进度（客户角度）', project: '项目进度（项目角度）', annotator: '标注员／质检员情况',
  assignment: '安排', idea: '想法', other: '其他',
}
const stateLabels = { queued: '排队中', running: '分析中', succeeded: '已完成', failed: '失败' }
const progressTracks = new Set(['customer', 'project', 'annotator'])
const canWrite = hasPermission('projects:write')
const visible = ref(true), mode = ref(props.initialMode), scope = ref('current'), period = ref('day')
const runs = ref([]), selected = ref(''), run = ref(null), hasMore = ref(false)
const error = ref(''), loading = ref(false), submitting = ref(false), applying = ref(false)
const importedIds = computed(() => new Set(run.value?.imports?.map(entry => entry.resultId)))
const canImport = computed(() => run.value?.state === 'succeeded' && run.value.results.some(
  item => progressTracks.has(item.category) && !importedIds.value.has(item.id),
))
const groupedResults = computed(() => Object.entries(categories).map(([key, label]) => ({
  key, label, items: run.value?.results?.filter(item => item.category === key) || [],
})).filter(group => group.items.length))
const controller = new AbortController()
let timer
let detailVersion = 0
let loadedCount = 0
const request = (suffix = '', options = {}) => chatRequest(`annotation-ai/${props.projectId}/runs${suffix}`, { ...options, signal: controller.signal })
const errorText = (cause, fallback) => cause.detail || cause.message || fallback

function runLabel(row) {
  const label = row.scheduledOn ? '工作日自动分析' : periods.find(option => option.value === row.period)?.label
  return `${formatBusinessDateTime(row.createdAt)} · ${label} · ${stateLabels[row.state]}`
}

async function loadDetail() {
  const id = selected.value
  const version = ++detailVersion
  if (run.value?.id !== id) run.value = null
  if (!id) return
  try {
    const data = await request(`/${id}`)
    if (version === detailVersion) run.value = data
  } catch (cause) {
    if (version === detailVersion && !controller.signal.aborted) error.value = errorText(cause, '读取分析结果失败')
  }
}

async function refresh() {
  if (loading.value || submitting.value || !visible.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await request()
    const recent = new Set(data.items.map(row => row.id))
    const older = loadedCount > 20 ? runs.value.filter(row => !recent.has(row.id)) : []
    runs.value = [...data.items, ...older]
    if (loadedCount <= 20) {
      loadedCount = data.items.length
      hasMore.value = data.hasMore
    }
    if (!runs.value.some(row => row.id === selected.value)) selected.value = runs.value[0]?.id || ''
    await loadDetail()
  } catch (cause) {
    if (!controller.signal.aborted) error.value = errorText(cause, '读取分析记录失败')
  } finally {
    loading.value = false
  }
}

async function loadOlder() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await request('', { params: { skip: runs.value.length } })
    const seen = new Set(runs.value.map(row => row.id))
    runs.value.push(...data.items.filter(row => !seen.has(row.id)))
    loadedCount = runs.value.length
    hasMore.value = data.hasMore
  } catch (cause) {
    if (!controller.signal.aborted) error.value = errorText(cause, '加载更早批次失败')
  } finally {
    loading.value = false
  }
}

function showHistory() {
  mode.value = 'history'
}

async function submit(autoApply) {
  if (submitting.value) return
  submitting.value = true
  applying.value = autoApply
  error.value = ''
  try {
    const data = await request('', { method: 'post', data: { period: period.value, autoApply, allVisible: scope.value === 'all' } })
    ElMessage.success(data.queued ? `已提交 ${data.queued} 个会话的 AI 分析` : '所选会话在此时段没有可分析的消息')
    showHistory()
  } catch (cause) {
    if (!controller.signal.aborted) error.value = errorText(cause, '提交分析失败')
  } finally {
    submitting.value = false
    applying.value = false
    if (mode.value === 'history') void refresh()
  }
}

async function addProgress() {
  if (submitting.value || !canImport.value) return
  const id = run.value.id
  submitting.value = true
  error.value = ''
  try {
    const data = await request(`/${id}/progress`, { method: 'post' })
    if (selected.value === id) {
      detailVersion++
      run.value = data.run
    }
    ElMessage.success(data.created ? `已加入 ${data.created} 条项目进度` : '对应进度已保存')
  } catch (cause) {
    if (!controller.signal.aborted) error.value = errorText(cause, '加入项目进度失败')
  } finally {
    submitting.value = false
  }
}

watch(mode, value => {
  clearInterval(timer)
  if (value === 'history') {
    void refresh()
    timer = setInterval(() => { if (runs.value.some(row => ['queued', 'running'].includes(row.state))) void refresh() }, 4000)
  }
}, { immediate: true })
onBeforeUnmount(() => { clearInterval(timer); controller.abort() })
</script>

<style scoped>
.chat-ai-fields { display: grid; gap: 10px; }
.chat-ai-fields strong { display: block; margin-bottom: 4px; }
.chat-ai-fields .el-radio-group { display: flex; flex-wrap: wrap; }
.chat-ai-muted { color: #64748b; }
.chat-ai-history { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.chat-ai-history .el-select { flex: 1 1 280px; }
.chat-ai-range { margin-bottom: 10px; }
.chat-ai-group { padding: 10px 0; border-bottom: 1px solid #e2e8f0; }
.chat-ai-group h3 { margin: 0; font-size: 14px; }
.chat-ai-group ul { margin: 8px 0 0; padding-left: 20px; }
.chat-ai-group li + li { margin-top: 8px; }
.chat-ai-summary { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>

<style>
.annotation-chat-ai-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.annotation-chat-ai-dialog > .el-dialog__header,
.annotation-chat-ai-dialog > .el-dialog__footer { flex: none; }
.annotation-chat-ai-dialog > .el-dialog__body { min-height: 0; flex: 1; overflow-y: auto; }
.annotation-chat-ai-dialog > .el-dialog__footer { border-top: 1px solid #e2e8f0; }
</style>
