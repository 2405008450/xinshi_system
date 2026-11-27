<template>
  <div v-if="!historyOnly || result?.first_overdue?.[kind]" class="word-count-deadline">
    <details v-if="!historyOnly" class="word-count-deadline__help">
    <summary>{{ label }}填写要求</summary>
    <ul>
      <li>10 份以内且不多于 5 万字，第二个工作日内填完。</li>
      <li>11–50 份且超过 5 万字、不多于 10 万字，第四个工作日内填完。</li>
      <li>51 份及以上且超过 10 万字，第六个工作日内填完。</li>
    </ul>
    <div>恰好 10 份、恰好 5 万字，或份数和字数分属不同档，均按第二个工作日执行。</div>
    <div>从客户接单次日起算，客户经理请假、休假等不计入工作日。</div>
    <div v-if="!result?.due_on">
      <span v-if="result?.calendar_error">{{ result.calendar_error }}</span>
      <span v-else-if="error">{{ error }}</span>
      <span v-else-if="loading">正在计算填写截止日…</span>
      <span v-else>有接单日期、客户经理、份数和字数后，系统将自动显示填写截止日。</span>
    </div>
    </details>
    <div class="word-count-deadline__result" role="status">
      <template v-if="!historyOnly">
      <strong v-if="result?.due_on">{{ label }}填写截止日 {{ result.due_on }}（第 {{ result.workdays }} 个工作日）</strong>
      <div v-if="result?.overdue?.[kind]" class="deadline-overdue">{{ label }}填写已逾期</div>
      </template>
      <div v-if="result?.first_overdue?.[kind]">首次逾期 {{ result.first_overdue[kind].overdue_on }}（原截止日 {{ result.first_overdue[kind].due_on }}）</div>
      <div v-if="result?.record_error">{{ result.record_error }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { normalizeWordCountMatrix } from '@/utils/wordCountMatrix'

const props = defineProps({
  receivedAt: String,
  managerId: String,
  matrix: Object,
  projectId: String,
  kind: { type: String, default: 'word_count' },
  historyOnly: Boolean,
  revision: [String, Object, Array],
})
const label = computed(() => props.kind === 'unit_price' ? '单价' : '工作量统计')

const receivedOn = computed(() => props.receivedAt ? businessDateTimeInputValue(props.receivedAt).slice(0, 10) : '')
const statistics = computed(() => Object.values(normalizeWordCountMatrix(props.matrix || {})))
const fileCount = computed(() => statistics.value.find(row => row.documents > 0)?.documents)
const wordCount = computed(() => statistics.value.find(row => row.words != null)?.words)
const result = ref(null)
const error = ref('')
const loading = ref(false)

const refresh = ref(0)
const refreshTimer = setInterval(() => { if (props.projectId) refresh.value++ }, 60_000)
onBeforeUnmount(() => clearInterval(refreshTimer))

watch([receivedOn, () => props.managerId, fileCount, wordCount, () => props.projectId, () => props.revision, refresh], ([date, managerId, files, words, projectId], previous, onCleanup) => {
  if (!projectId || previous?.[4] !== projectId) result.value = null
  error.value = ''
  loading.value = Boolean(projectId || (date && managerId && Number.isInteger(files) && Number.isInteger(words)))
  if (!loading.value) return

  const request = new AbortController()
  const timer = setTimeout(async () => {
    try {
      const data = projectId
        ? await api.post(`/projects/translation/${projectId}/entry-deadlines`, null, { signal: request.signal, skipDraftSubmit: true })
        : await api.get('/projects/translation/word-count-deadline', {
          params: { received_on: date, manager_id: managerId, file_count: files, word_count: words },
          signal: request.signal,
        })
      if (!request.signal.aborted) result.value = data
    } catch (reason) {
      if (!request.signal.aborted) error.value = getLocalizedErrorMessage(reason, '填写截止日计算失败')
    } finally {
      if (!request.signal.aborted) loading.value = false
    }
  }, 400)
  onCleanup(() => {
    clearTimeout(timer)
    request.abort()
  })
}, { immediate: true })
</script>

<style scoped>
.word-count-deadline {
  width: 100%;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.65;
}
.word-count-deadline ul {
  margin: 4px 0;
  padding-inline-start: 18px;
}
.word-count-deadline__help summary { cursor: pointer; width: fit-content; font-weight: 600; }
.word-count-deadline__result {
  margin-top: 4px;
}
.word-count-deadline__result strong {
  color: var(--el-text-color-primary);
}
.deadline-overdue {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
