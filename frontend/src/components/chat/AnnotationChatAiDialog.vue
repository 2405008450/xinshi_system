<template>
  <DraggableFormDialog v-model="visible" :title="mode === 'run' ? '运行 AI 分析' : 'AI 分析进度与结果'"
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
          <el-descriptions-item label="运行状态">{{ stateLabels[run.state] }}</el-descriptions-item>
          <el-descriptions-item v-if="run.coverage" label="聊天记录统计">
            共 {{ run.coverage.total }} 条 · 已分类 {{ run.coverage.classified }} 条 · 未分类 {{ run.coverage.unclassified }} 条
          </el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="run.error || run.importError" :title="run.error || run.importError" type="error" :closable="false" />
        <template v-if="run.state === 'succeeded'">
          <el-empty v-if="!run.results.length" description="此时段没有可分类的聊天要点" :image-size="60" />
          <section v-for="group in groupedResults" :key="`${run.id}:${group.key}`" class="chat-ai-group">
            <h3>{{ group.label }}（{{ group.items.length }}）</h3>
            <ul>
              <li v-for="item in group.items" :key="item.id">
                <div class="chat-ai-result">
                  <el-checkbox v-if="canWrite && progressTracks.has(item.category) && !importedIds.has(item.id)"
                    v-model="checkedIds" :value="item.id" :aria-label="`选择进度：${item.summary}`" :disabled="submitting" />
                  <div class="chat-ai-summary">{{ item.summary }}</div>
                </div>
                <small class="chat-ai-muted">{{ formatBusinessDateTime(item.effectiveAt) }}<span v-if="importedIds.has(item.id)"> · 已加入项目进度</span></small>
                <details v-if="item.sources.length" class="chat-ai-sources" @toggle="loadSources(item.id, $event.currentTarget.open)">
                  <summary>查看 {{ item.sources.length }} 条来源消息</summary>
                  <template v-if="sourceById[item.id]">
                    <p v-if="sourceById[item.id].loading" role="status">正在读取来源消息…</p>
                    <p v-else-if="sourceById[item.id].error" role="alert">{{ sourceById[item.id].error }} <el-button link @click="loadSources(item.id, true)">重试</el-button></p>
                    <template v-else>
                      <div v-for="source in sourceById[item.id].items" :key="source.id" class="chat-ai-source">
                        <strong>{{ source.senderName }}</strong> · {{ formatBusinessDateTime(source.createdAt) }}
                        <div class="chat-ai-summary"><ScreenshotText :text="source.content" :chat-message-id="source.id" chat-kind="annotation" /></div>
                      </div>
                      <small v-if="sourceById[item.id].unavailable" class="chat-ai-muted">{{ sourceById[item.id].unavailable }} 条来源消息已撤回或不可查看</small>
                    </template>
                  </template>
                </details>
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
        <el-button :disabled="submitting" @click="showHistory">返回分析进度</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">运行分析</el-button>
      </template>
      <template v-else>
        <el-button v-if="canWrite && run?.state === 'succeeded'" :disabled="!selectedProgressIds.length" :loading="submitting" @click="addProgress">加入项目进度{{ selectedProgressIds.length ? `（${selectedProgressIds.length}）` : '' }}</el-button>
        <el-button type="primary" :disabled="submitting" @click="mode = 'run'; error = ''">新建分析</el-button>
      </template>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { chatRequest } from '@/api/projectChat'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { hasPermission } from '@/utils/permission'

const props = defineProps({ projectId: { type: String, required: true } })
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
const visible = ref(true), mode = ref('history'), scope = ref('current'), period = ref('day')
const runs = ref([]), selected = ref(''), run = ref(null), hasMore = ref(false)
const error = ref(''), loading = ref(false), submitting = ref(false)
const checkedIds = ref([])
const sourceById = ref({})
const importedIds = computed(() => new Set(run.value?.imports?.map(entry => entry.resultId)))
const selectedProgressIds = computed(() => run.value?.state === 'succeeded' ? run.value.results
  .filter(item => progressTracks.has(item.category) && checkedIds.value.includes(item.id) && !importedIds.value.has(item.id))
  .map(item => item.id) : [])
const groupedResults = computed(() => Object.entries(categories).map(([key, label]) => ({
  key, label, items: run.value?.results?.filter(item => item.category === key) || [],
})).filter(group => group.items.length))
const controller = new AbortController()
let timer
let detailVersion = 0
let loadedCount = 0
const request = (suffix = '', options = {}) => chatRequest(`annotation-ai/${props.projectId}/runs${suffix}`, { ...options, signal: controller.signal })
const errorText = (cause, fallback) => cause.detail || cause.message || fallback
watch(selected, () => { checkedIds.value = []; sourceById.value = {} }, { flush: 'sync' })

async function loadSources(resultId, expanded) {
  const runId = run.value?.id
  if (!expanded || !runId || runId !== selected.value || sourceById.value[resultId]?.loading) return
  const cache = sourceById.value
  cache[resultId] = { loading: true }
  try {
    cache[resultId] = await request(`/${runId}/results/${resultId}/sources`)
  } catch (cause) {
    if (!controller.signal.aborted) cache[resultId] = { error: errorText(cause, '读取来源消息失败') }
  }
}

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
    if (!runs.value.some(row => row.id === selected.value)) {
      selected.value = (runs.value.find(row => row.state === 'running') ||
        runs.value.find(row => row.state === 'queued') || runs.value[0])?.id || ''
    }
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

async function submit() {
  if (submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const data = await request('', { method: 'post', data: { period: period.value, allVisible: scope.value === 'all' } })
    ElMessage.success(data.queued ? `已提交 ${data.queued} 个会话的 AI 分析` : '所选会话在此时段没有可分析的消息')
    if (data.queued) selected.value = ''
    showHistory()
  } catch (cause) {
    if (!controller.signal.aborted) error.value = errorText(cause, '提交分析失败')
  } finally {
    submitting.value = false
    if (mode.value === 'history') void refresh()
  }
}

async function addProgress() {
  if (submitting.value || !selectedProgressIds.value.length) return
  const id = run.value.id
  submitting.value = true
  error.value = ''
  try {
    const data = await request(`/${id}/progress`, { method: 'post', data: { resultIds: selectedProgressIds.value } })
    if (selected.value === id) {
      detailVersion++
      run.value = { ...data.run, coverage: run.value?.coverage }
      checkedIds.value = []
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
.chat-ai-result { display: flex; align-items: flex-start; gap: 8px; }
.chat-ai-result .el-checkbox { height: 22px; flex: none; margin-right: 0; }
.chat-ai-sources summary { cursor: pointer; color: var(--el-color-primary); font-size: 12px; }
.chat-ai-source { padding: 8px; margin: 4px 0; background: #eff6ff; border-radius: 4px; }
</style>

<style>
.annotation-chat-ai-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.annotation-chat-ai-dialog > .el-dialog__header,
.annotation-chat-ai-dialog > .el-dialog__footer { flex: none; }
.annotation-chat-ai-dialog > .el-dialog__body { min-height: 0; flex: 1; overflow-y: auto; }
.annotation-chat-ai-dialog > .el-dialog__footer { border-top: 1px solid #e2e8f0; }
</style>
