<template>
  <section class="source-ai-panel" aria-label="AI来源分析" data-auto-draft="off" :aria-busy="busy">
    <div class="source-ai-heading"><strong>{{ dimension === 'keyword' ? '来源关键词 AI 分析与分类' : '客户来源 AI 分析与分类' }}</strong><span>复用“我的思考与发散”AI 服务</span></div>
    <p class="source-ai-note">发送当前筛选范围内的原始来源或关键词、咨询次数与关联客户数。结果提供分类建议，原始记录保留。</p>
    <p class="source-ai-note">{{ context.scope }}；本次 {{ context.itemCount }}/{{ context.totalItems }} 个原始项，覆盖 {{ context.covered }}/{{ context.total }} 条咨询。</p>
    <el-alert v-if="context.partial" type="info" :closable="false" :title="`受同一 AI 接口 ${maxChars} 字上限限制，本次按数量选择前 ${context.itemCount} 项；其余 ${context.omitted} 条咨询未参与分析，可缩小日期范围后重试。`" />
    <div class="source-ai-qa" :class="{ 'source-ai-qa--expanded': answerOpen }">
      <div class="source-ai-question">
        <AppForm :model="form" label-position="top" :saved-sync-enabled="false">
          <el-form-item label="问（可选）">
            <el-input v-model="form.instruction" type="textarea" :rows="2" maxlength="1000" show-word-limit placeholder="输入补充分析要求，Enter 提交，Shift + Enter 换行" :disabled="busy || changing" @keydown.enter="submitOnEnter" />
          </el-form-item>
        </AppForm>
        <div class="source-ai-actions">
          <el-button type="primary" :disabled="!canSubmit" :loading="changing && !busy" @click="submit">{{ job?.state === 'succeeded' ? '重新分析与分类' : '开始分析与分类' }}</el-button>
          <el-button v-if="busy" :disabled="changing || job?.state === 'cancelling'" @click="cancel">取消 AI 任务</el-button>
          <el-button v-if="!busy" :disabled="changing" @click="refresh">刷新 AI 状态</el-button>
        </div>
        <p class="source-ai-note" role="status">{{ error || statusText }}</p>
        <button v-if="job" type="button" class="source-ai-question-toggle" :aria-expanded="answerOpen" :aria-controls="answerId" @click="answerOpen = !answerOpen">
          <span class="source-ai-question-text">{{ submittedQuestion }}</span>
          <span class="source-ai-toggle-label">{{ answerOpen ? '收起答案' : '展开答案' }}</span>
        </button>
      </div>
      <section v-if="job" v-show="answerOpen" :id="answerId" class="source-ai-result" aria-label="答">
        <div class="source-ai-heading">
          <strong>答</strong>
          <el-button v-if="job.state === 'succeeded'" link type="primary" @click="copy">复制结果</el-button>
        </div>
        <template v-if="job.state === 'succeeded'">
          <p class="source-ai-note">{{ resultContext?.scope }}；覆盖 {{ resultContext?.covered }}/{{ resultContext?.total }} 条咨询，{{ resultContext?.itemCount }} 个原始项。</p>
          <div class="source-ai-result-text">{{ job.result }}</div>
          <el-alert v-if="job.truncated" type="info" :closable="false" title="本次结果达到 AI 服务输出上限，可缩小日期范围或补充更具体的问题后再次分析。" />
        </template>
        <p v-else class="source-ai-note">{{ error || statusText }}</p>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, useId, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppForm from './AppForm.vue'
import { getThoughtAiState, createThoughtAiJob, cancelThoughtAiJob } from '@/api/thoughtsAi'
import { buildCustomerSourceAiContext } from '@/utils/customerSourceAi'

const props = defineProps({ dimension: { type: String, required: true }, stats: { type: Object, required: true }, start: String, end: String, granularity: String, loading: Boolean })
const form = reactive({ instruction: '' })
const answerId = useId()
const answerOpen = ref(false)
const submittedQuestion = ref('')
const job = ref(null), enabled = ref(false), loadingState = ref(true), changing = ref(false), error = ref(''), otherBusy = ref(false), resultContext = ref(null), maxChars = ref(6000)
const context = computed(() => buildCustomerSourceAiContext({ ...props, instruction: form.instruction, maxChars: maxChars.value }))
const busy = computed(() => ['queued', 'running', 'cancelling'].includes(job.value?.state))
const canSubmit = computed(() => enabled.value && !loadingState.value && !props.loading && !changing.value && !busy.value && !otherBusy.value && context.value.itemCount > 0)
const statusText = computed(() => loadingState.value ? '正在连接 AI 服务……' : !enabled.value ? 'AI 服务尚未启用，请联系管理员确认与工作台共用的算力配置' : busy.value ? job.value.message || '已提交，正在排队分析……' : job.value?.state === 'succeeded' ? '分析已完成' : otherBusy.value ? '你已有其他 AI 任务正在处理，请完成后刷新 AI 状态' : job.value?.state === 'failed' || job.value?.state === 'cancelled' ? job.value.message || 'AI 任务已结束，可重新提交' : context.value.itemCount === 0 ? '当前范围暂无可分析数据' : '点击后提交当前聚合数据，繁忙时自动排队')
const owner = localStorage.getItem('user_id')
const aiScope = computed(() => props.dimension === 'keyword' ? 'source_keyword' : 'customer_source')
let disposed = false, generation = 0, scopeVersion = 0, controller, timer
const current = () => !disposed && localStorage.getItem('user_id') === owner
function stopRead() { ++generation; clearTimeout(timer); controller?.abort() }
function schedule() { if (current() && (busy.value || otherBusy.value)) timer = setTimeout(refresh, 1500) }
async function refresh() {
  stopRead()
  if (!current()) return
  const sequence = generation
  controller = new AbortController()
  try {
    const data = await getThoughtAiState({ params: { scope: aiScope.value }, signal: controller.signal })
    if (!current() || sequence !== generation) return
    enabled.value = data.enabled
    maxChars.value = Math.min(6000, data.max_chars || 6000)
    const latestBusy = ['queued', 'running', 'cancelling'].includes(data.job?.state)
    otherBusy.value = Boolean((data.busy || latestBusy) && !(latestBusy && data.job?.id === job.value?.id))
    error.value = ''
    // 工作台与分析共用本人队列；不能将个人思考的结果显示成客户来源分析。
    if (job.value && data.job?.id === job.value.id) job.value = data.job
    else if (busy.value) { job.value = null; answerOpen.value = false; error.value = '当前 AI 任务已变化，请重新分析' }
  } catch (err) {
    if (current() && sequence === generation) error.value = err.detail || err.message || 'AI 服务连接失败，请刷新状态重试'
  } finally {
    if (current() && sequence === generation) { loadingState.value = false; schedule() }
  }
}
function submitOnEnter(event) {
  if (event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  submit()
}
async function submit() {
  if (!canSubmit.value) return
  stopRead(); changing.value = true; error.value = ''
  const version = scopeVersion, snapshot = { ...context.value }
  const question = form.instruction.trim() || (props.dimension === 'keyword' ? '分析并分类来源关键词' : '分析并分类客户来源')
  try {
    const data = await createThoughtAiJob({ scope: aiScope.value, action: 'organize', content: snapshot.content })
    if (!current() || version !== scopeVersion) {
      if (localStorage.getItem('user_id') === owner) await cancelThoughtAiJob(data.id).catch(() => {})
      return
    }
    job.value = data; resultContext.value = snapshot
    submittedQuestion.value = question
    answerOpen.value = false
  } catch (err) {
    if (current() && version === scopeVersion) error.value = err.detail || err.message || 'AI 提交失败，请重试'
  } finally {
    changing.value = false; schedule()
  }
}
async function cancel() {
  if (!busy.value || changing.value) return
  stopRead(); changing.value = true
  const version = scopeVersion, id = job.value.id
  try {
    const data = await cancelThoughtAiJob(id)
    if (current() && version === scopeVersion) { job.value = data; error.value = '' }
  } catch (err) {
    if (current() && version === scopeVersion) error.value = err.detail || err.message || '取消失败，请重试'
  } finally { changing.value = false; schedule() }
}
function invalidate() {
  const id = busy.value ? job.value.id : null
  ++scopeVersion; stopRead(); job.value = null; resultContext.value = null; error.value = ''; otherBusy.value = false
  answerOpen.value = false
  if (id && localStorage.getItem('user_id') === owner) cancelThoughtAiJob(id).catch(() => {})
}
async function copy() {
  try { await navigator.clipboard.writeText(job.value.result); ElMessage.success('已复制分析结果') }
  catch { ElMessage.warning('请选中结果文字手动复制') }
}
watch([() => props.dimension, () => props.start, () => props.end, () => props.granularity, () => props.stats], () => { invalidate(); if (current()) refresh() })
onMounted(refresh)
onBeforeUnmount(() => { invalidate(); disposed = true })
</script>

<style scoped>
.source-ai-panel { margin: 16px 0; padding: 16px; border: 1px solid var(--el-color-primary-light-7); border-radius: 8px; background: var(--el-fill-color-extra-light); min-width: 0; }
.source-ai-heading, .source-ai-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.source-ai-heading span, .source-ai-note { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.source-ai-actions :deep(.el-button) { margin-left: 0; }
.source-ai-panel :deep(.el-form-item) { margin: 14px 0; }
.source-ai-qa { display: grid; gap: 16px; align-items: start; }
.source-ai-qa--expanded { grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); }
.source-ai-question, .source-ai-result { min-width: 0; }
.source-ai-question-toggle { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; width: 100%; padding: 10px 12px; border: 1px solid var(--el-border-color); border-radius: 6px; background: var(--el-bg-color); color: var(--el-text-color-primary); font: inherit; text-align: left; cursor: pointer; }
.source-ai-question-toggle:hover { border-color: var(--el-color-primary); }
.source-ai-question-text { white-space: pre-wrap; overflow-wrap: anywhere; min-width: 0; }
.source-ai-toggle-label { flex-shrink: 0; color: var(--el-color-primary); }
.source-ai-result { background: var(--el-bg-color); margin-top: 14px; padding: 14px; border-radius: 6px; }
.source-ai-result-text { max-height: 460px; overflow-y: auto; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.8; }
@media (max-width: 720px) { .source-ai-qa--expanded { grid-template-columns: minmax(0, 1fr); } .source-ai-result { margin-top: 0; } }
@media (max-width: 600px) { .source-ai-panel, .source-ai-result { padding: 10px; } }
</style>
