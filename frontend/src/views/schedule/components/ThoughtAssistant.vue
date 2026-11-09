<template>
  <section class="thought-assistant" aria-label="AI 思考助手" :aria-busy="busy">
    <div class="assistant-heading">
      <strong>AI 思考助手</strong>
      <span>点击后发送当前文字，繁忙时自动排队</span>
    </div>
    <p class="assistant-hint">每次最多 6000 字，暂不读取截图。结果保留 24 小时，追加到笔记后随笔记长期保存。</p>
    <div class="assistant-actions">
      <el-button v-for="action in actions" :key="action.key" :disabled="!canSubmit" @click="submit(action.key)">{{ action.label }}</el-button>
      <el-button v-if="busy" :disabled="changing || job?.state === 'cancelling'" @click="cancel">取消任务</el-button>
      <el-button v-if="error" text @click="refresh">重新连接</el-button>
    </div>
    <p v-if="loading || !enabled || busy || error" role="status" class="assistant-status">
      {{ error || (loading ? '正在连接 AI 服务……' : !enabled ? 'AI 服务尚未启用，笔记仍可正常保存' : statusText) }}
    </p>
    <p v-if="text.length > 6000" class="assistant-status">当前文字 {{ text.length }} 字，请精简到 6000 字以内再提交。</p>
    <div v-if="job && !busy" class="assistant-result">
      <template v-if="job.state === 'succeeded'">
        <div class="result-heading">
          <strong>{{ actionLabel }}结果</strong>
          <span>{{ formatBusinessDateTime(job.created_at) }}</span>
        </div>
        <div class="result-text">{{ job.result }}</div>
        <p v-if="job.truncated" class="assistant-status">本次结果达到长度上限，可缩小问题范围后再次生成。</p>
        <div class="assistant-actions">
          <el-button type="primary" :disabled="appendedId === job.id" @click="append">{{ appendedId === job.id ? '已追加到笔记' : '追加到笔记' }}</el-button>
          <el-button @click="copy">复制结果</el-button>
        </div>
      </template>
      <p v-else role="status">{{ job.message || (job.state === 'cancelled' ? '已取消' : '生成失败，请重试') }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index'
import { screenshotText } from '@/utils/screenshotReferences'
import { formatBusinessDateTime } from '@/utils/dateTime'

const props = defineProps({ content: { type: String, default: '' } })
const emit = defineEmits(['append'])
const actions = [{ key: 'organize', label: '帮我梳理' }, { key: 'explore', label: '继续发散' }, { key: 'todos', label: '提炼待办' }]
const job = ref(null), enabled = ref(false), loading = ref(true), changing = ref(false), error = ref(''), appendedId = ref('')
const text = computed(() => screenshotText(props.content).trim())
const busy = computed(() => ['queued', 'running', 'cancelling'].includes(job.value?.state))
const canSubmit = computed(() => enabled.value && !loading.value && !changing.value && !busy.value && text.value.length > 0 && text.value.length <= 6000)
const actionLabel = computed(() => actions.find(item => item.key === job.value?.action)?.label || 'AI')
const statusText = computed(() => job.value?.state === 'queued' ? '已提交，正在排队……' : job.value?.message || '正在生成……')
let timer, controller, disposed = false, generation = 0
const owner = localStorage.getItem('user_id')
const current = () => !disposed && localStorage.getItem('user_id') === owner

function stopRead() {
  generation++
  clearTimeout(timer)
  controller?.abort()
}

async function refresh() {
  stopRead()
  if (!current()) return
  const sequence = generation
  controller = new AbortController()
  try {
    const data = await api.get('/thoughts-ai/latest', { signal: controller.signal })
    if (!current() || sequence !== generation) return
    enabled.value = data.enabled
    job.value = data.job
    error.value = ''
  } catch (err) {
    if (current() && sequence === generation) error.value = err.detail || err.message || 'AI 服务连接失败，笔记仍可正常保存'
  } finally {
    if (current() && sequence === generation) {
      loading.value = false
      if (busy.value) timer = setTimeout(refresh, 2000)
    }
  }
}

async function submit(action) {
  if (!canSubmit.value) return
  stopRead()
  changing.value = true
  error.value = ''
  try {
    const data = await api.post('/thoughts-ai/jobs', { action, content: text.value })
    if (current()) { job.value = data; appendedId.value = '' }
  } catch (err) {
    if (current()) error.value = err.detail || err.message || 'AI 提交失败，请重试'
  } finally {
    changing.value = false
    if (current()) timer = setTimeout(refresh, 1000)
  }
}

async function cancel() {
  if (!busy.value || changing.value) return
  stopRead()
  changing.value = true
  try {
    const data = await api.post(`/thoughts-ai/jobs/${job.value.id}/cancel`)
    if (current()) { job.value = data; error.value = '' }
  } catch (err) {
    if (current()) error.value = err.detail || err.message || '取消失败，请重试'
  } finally {
    changing.value = false
    if (current()) timer = setTimeout(refresh, 1000)
  }
}

function append() {
  if (!current() || job.value?.state !== 'succeeded' || appendedId.value === job.value.id) return
  const addition = `【${actionLabel.value}】\n${job.value.result}`
  if ((props.content ? `${props.content}\n\n` : '').length + addition.length > 30000) {
    ElMessage.warning('追加后超过笔记 30000 字上限，请先精简笔记或复制结果')
    return
  }
  emit('append', addition)
  appendedId.value = job.value.id
}

async function copy() {
  try { await navigator.clipboard.writeText(job.value.result); ElMessage.success('结果已复制') }
  catch { ElMessage.warning('复制失败，请选中结果文字后手动复制') }
}

onMounted(refresh)
onBeforeUnmount(() => { disposed = true; stopRead() })
</script>

<style scoped>
.thought-assistant{margin-top:18px;padding:16px;border:1px solid #dbe4ef;border-radius:8px;background:#f8fafc;min-width:0}
.assistant-heading,.result-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px 16px}
.assistant-heading span,.assistant-hint,.result-heading span,.assistant-status{font-size:12px;color:#64748b}
.assistant-hint{margin:8px 0 12px}.assistant-actions{display:flex;flex-wrap:wrap;gap:8px}.assistant-actions :deep(.el-button){margin-left:0}
.assistant-result{margin-top:14px;padding:14px;background:#fff;border:1px solid #e2e8f0;border-radius:6px}
.result-text{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow-y:auto;margin:12px 0;line-height:1.7;color:#334155}
.assistant-status{margin:10px 0 0}
@media(max-width:600px){.thought-assistant,.assistant-result{padding:10px}.assistant-heading{align-items:flex-start;flex-direction:column}}
</style>
