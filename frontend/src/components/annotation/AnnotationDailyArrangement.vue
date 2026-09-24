<template>
  <section
    ref="panelRef"
    class="daily-arrangement"
    :class="{ 'is-fallback-fullscreen': fallbackFullscreen }"
    v-loading="loading"
  >
    <header class="daily-arrangement__header">
      <div>
        <h3>{{ selectedDate === today ? '今日安排' : '当日安排' }}</h3>
        <p>{{ formatNoteDate(selectedDate) }} · 团队共享安排</p>
      </div>
      <div class="daily-arrangement__actions">
        <el-date-picker
          :model-value="selectedDate"
          type="date"
          value-format="YYYY-MM-DD"
          format="YYYY年MM月DD日"
          :clearable="false"
          :disabled="saving || loading"
          :teleported="!fullscreenActive"
          aria-label="安排日期"
          @update:model-value="switchDate"
        />
        <el-button :disabled="saving || loading || selectedDate === today" @click="switchDate(today)">返回今天</el-button>
        <el-button :loading="loading" :disabled="saving" @click="refreshNotes">刷新</el-button>
        <el-button :icon="FullScreen" @click="toggleFullscreen">
          {{ fullscreenActive ? '退出全屏' : '全屏查看' }}
        </el-button>
        <el-button v-if="canEdit && !editing" type="primary" :disabled="loading || !noteLoaded" @click="startEditing">编辑内容</el-button>
      </div>
    </header>

    <div class="daily-arrangement__body">
      <template v-if="editing">
        <RichTextComposer
          :key="selectedDate"
          v-model="draftContent"
          format-colors
          min-height="360px"
          placeholder="请输入所选日期的项目安排、人员协调或需要团队注意的事项…"
        />
        <div class="daily-arrangement__editor-actions">
          <el-button :disabled="saving" @click="cancelEditing">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveNote">保存</el-button>
        </div>
      </template>

      <template v-else>
        <div v-if="note?.updatedAt" class="daily-arrangement__meta">
          最近由 {{ note.updatedByName || '未知用户' }} 编辑于 {{ formatDateTime(note.updatedAt) }}
        </div>
        <RichTextContent
          v-if="hasContent(note?.contentJson)"
          :document="note.contentJson"
          class="daily-arrangement__document daily-arrangement__preview"
        />
        <el-empty v-else-if="!loading" :description="noteLoaded ? '所选日期暂无安排' : '安排加载失败，请刷新重试'" :image-size="96">
          <el-button v-if="canEdit && noteLoaded" type="primary" @click="startEditing">填写当日安排</el-button>
        </el-empty>
      </template>
    </div>
    <section class="daily-arrangement__history" v-loading="historyLoading">
      <h3>历史安排</h3>
      <p>按安排日期从新到旧排列，可查看或编辑对应日期的安排。</p>
      <el-empty v-if="!historyLoading && !history.length" description="暂无历史安排" :image-size="80" />
      <article v-for="item in history" :key="item.id" class="daily-arrangement__card">
        <header>
          <div>
            <strong>{{ formatNoteDate(item.noteDate) }}</strong>
            <span>由 {{ item.updatedByName || '未知用户' }} 更新于 {{ formatDateTime(item.updatedAt) }}</span>
          </div>
          <el-button link type="primary" :disabled="saving || loading" @click="openHistoryNote(item)">
            {{ canEdit ? '编辑这一天' : '查看这一天' }}
          </el-button>
        </header>
        <RichTextContent :document="item.contentJson" class="daily-arrangement__preview" />
      </article>
      <el-button v-if="hasMoreHistory" :loading="historyLoading" @click="loadHistory(false)">加载更多</el-button>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { getArrangementDailyNote, getArrangementDailyNotes, saveArrangementDailyNote } from '@/api/annotationOps'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { formatDateTimeMinute } from '@/utils/dateTime'

const props = defineProps({ canEdit: { type: Boolean, default: false } })

const BUSINESS_TIME_ZONE = 'Asia/Hong_Kong'
const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const cloneDocument = value => JSON.parse(JSON.stringify(value || emptyDocument()))

const panelRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const note = ref(null)
const noteLoaded = ref(false)
const history = ref([])
const historyLoading = ref(false)
const hasMoreHistory = ref(false)
let historyRequestId = 0
const draftContent = ref(emptyDocument())
const originalContent = ref(JSON.stringify(emptyDocument()))
const nativeFullscreen = ref(false)
const fallbackFullscreen = ref(false)

const today = computed(() => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date()).filter(item => item.type !== 'literal').map(item => [item.type, item.value]))
  return `${parts.year}-${parts.month}-${parts.day}`
})
const selectedDate = ref(today.value)
const formatNoteDate = value => value.replace(/(\d{4})-(\d{2})-(\d{2})/, '$1年$2月$3日')
const fullscreenActive = computed(() => nativeFullscreen.value || fallbackFullscreen.value)
const isDirty = computed(() => editing.value && JSON.stringify(draftContent.value) !== originalContent.value)

function hasContent(document) {
  const containsText = node => Boolean(node?.text?.trim()) || (node?.content || []).some(containsText)
  return Boolean(document && containsText(document))
}

async function loadNote() {
  loading.value = true
  noteLoaded.value = false
  note.value = null
  editing.value = false
  try {
    note.value = await getArrangementDailyNote(selectedDate.value)
    noteLoaded.value = true
    return true
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '当日安排加载失败'))
    return false
  } finally {
    loading.value = false
  }
}

async function loadHistory(reset = true) {
  if (historyLoading.value && !reset) return
  const requestId = ++historyRequestId
  historyLoading.value = true
  try {
    const rows = await getArrangementDailyNotes({ skip: reset ? 0 : history.value.length, limit: 20 })
    if (requestId !== historyRequestId) return
    history.value = reset ? rows : [...history.value, ...rows]
    hasMoreHistory.value = rows.length === 20
  } catch (error) {
    if (requestId === historyRequestId) ElMessage.error(getLocalizedErrorMessage(error, '历史安排加载失败'))
  } finally {
    if (requestId === historyRequestId) historyLoading.value = false
  }
}

async function switchDate(value) {
  if (!value || saving.value || loading.value) return false
  if (!await confirmDiscard()) return false
  selectedDate.value = value
  return loadNote()
}

async function refreshNotes() {
  if (saving.value || loading.value || !await confirmDiscard()) return
  await Promise.all([loadNote(), loadHistory()])
}

async function openHistoryNote(item) {
  if (!await switchDate(item.noteDate)) return
  if (props.canEdit) startEditing()
  panelRef.value?.querySelector('.daily-arrangement__header')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function startEditing() {
  if (!props.canEdit || loading.value || !noteLoaded.value) return
  draftContent.value = cloneDocument(note.value?.contentJson)
  originalContent.value = JSON.stringify(draftContent.value)
  editing.value = true
}

async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '放弃修改', {
      type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑',
      appendTo: fullscreenActive.value ? panelRef.value : document.body,
    })
    return true
  } catch {
    return false
  }
}

async function cancelEditing() {
  if (await confirmDiscard()) editing.value = false
}

async function saveNote() {
  if (saving.value || loading.value || !noteLoaded.value) return
  if (!hasContent(draftContent.value)) {
    ElMessage.warning('请输入当日安排内容')
    return
  }
  saving.value = true
  try {
    note.value = await saveArrangementDailyNote(selectedDate.value, {
      contentJson: draftContent.value,
      expectedUpdatedAt: note.value?.updatedAt,
    })
    editing.value = false
    ElMessage.success('当日安排已保存')
    await loadHistory()
  } catch (error) {
    const message = getLocalizedErrorMessage(error, '当日安排保存失败')
    ElMessage.error(error?.response?.status === 409 ? `${message}，请刷新后重试` : message)
  } finally {
    saving.value = false
  }
}

async function toggleFullscreen() {
  if (fallbackFullscreen.value) {
    fallbackFullscreen.value = false
    return
  }
  if (document.fullscreenElement) {
    await document.exitFullscreen()
    return
  }
  if (!panelRef.value?.requestFullscreen) {
    fallbackFullscreen.value = true
    return
  }
  try {
    await panelRef.value.requestFullscreen()
    if (!document.fullscreenElement) fallbackFullscreen.value = true
  } catch {
    fallbackFullscreen.value = true
  }
}

function handleFullscreenChange() {
  nativeFullscreen.value = document.fullscreenElement === panelRef.value
}

function handleKeydown(event) {
  if (event.key === 'Escape' && fallbackFullscreen.value) fallbackFullscreen.value = false
}

const formatDateTime = value => formatDateTimeMinute(value) || '-'

onMounted(() => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('keydown', handleKeydown)
  loadNote()
  loadHistory()
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.daily-arrangement { min-height: 480px; padding: 20px; background: var(--el-bg-color); overflow: auto; }
.daily-arrangement__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-lighter); }
.daily-arrangement__header h3 { margin: 0; font-size: 20px; }
.daily-arrangement__header p { margin: 6px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.daily-arrangement__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.daily-arrangement__actions .el-button + .el-button { margin-left: 0; }
.daily-arrangement__body { max-width: 1120px; margin: 0 auto; padding: 22px 4px; }
.daily-arrangement__meta { margin-bottom: 16px; color: var(--el-text-color-secondary); font-size: 13px; }
.daily-arrangement__document { min-height: 300px; }
.daily-arrangement__editor-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.daily-arrangement__history { max-width: 1120px; margin: 0 auto; border-top: 1px solid var(--el-border-color-lighter); padding-top: 20px; }
.daily-arrangement__history > h3 { margin: 0 0 8px; font-size: 17px; font-weight: 600; }
.daily-arrangement__history > p { margin: 0 0 20px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.daily-arrangement__card { padding: 20px 24px; margin-bottom: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; background: var(--el-bg-color); overflow-wrap: anywhere; }
.daily-arrangement__card header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 18px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-lighter); }
.daily-arrangement__card header strong { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); }
.daily-arrangement__card header span { display: block; margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.daily-arrangement__preview { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 15px; line-height: 1.9; color: var(--el-text-color-primary); overflow-wrap: anywhere; }
.daily-arrangement__preview :deep(.tiptap) { padding: 0; }
.daily-arrangement__preview :deep(p) { margin: 0 0 12px; }
.daily-arrangement__preview :deep(ul),.daily-arrangement__preview :deep(ol) { margin: 12px 0; padding-left: 1.8em; list-style-position: outside; }
.daily-arrangement__preview :deep(ol) { list-style-type: decimal; }
.daily-arrangement__preview :deep(ul) { list-style-type: disc; }
.daily-arrangement__preview :deep(li) { padding-left: 6px; margin: 8px 0; }
.daily-arrangement__preview :deep(li::marker) { color: var(--el-text-color-secondary); font-weight: 600; }
.daily-arrangement__preview :deep(li > p) { margin: 0; }
.daily-arrangement__preview :deep(h1),.daily-arrangement__preview :deep(h2),.daily-arrangement__preview :deep(h3) { margin: 20px 0 12px; font-weight: 600; line-height: 1.5; }
.daily-arrangement__preview :deep(h1) { font-size: 22px; }
.daily-arrangement__preview :deep(h2) { font-size: 19px; }
.daily-arrangement__preview :deep(h3) { font-size: 17px; }
.daily-arrangement__preview :deep(blockquote) { margin: 14px 0; padding: 10px 16px; border-left: 3px solid var(--el-border-color); background: var(--el-fill-color-light); }
.daily-arrangement__preview :deep(.tiptap > :first-child) { margin-top: 0; }
.daily-arrangement__preview :deep(.tiptap > :last-child) { margin-bottom: 0; }
.daily-arrangement__actions :deep(.el-date-editor) { width: 190px; max-width: 100%; }
.daily-arrangement:fullscreen,.daily-arrangement.is-fallback-fullscreen { width: 100vw; height: 100vh; min-height: 100vh; padding: 24px 32px; background: var(--el-bg-color); }
.daily-arrangement.is-fallback-fullscreen { position: fixed; inset: 0; z-index: 3000; }
@media (max-width: 640px) {
  .daily-arrangement { padding: 16px; }
  .daily-arrangement__header { flex-direction: column; }
  .daily-arrangement__actions { width: 100%; justify-content: flex-start; }
  .daily-arrangement__card { padding: 16px; }
  .daily-arrangement__card header { align-items: flex-start; }
  .daily-arrangement__card header .el-button { flex-shrink: 0; }
  .daily-arrangement:fullscreen,.daily-arrangement.is-fallback-fullscreen { padding: 16px; }
}
</style>
