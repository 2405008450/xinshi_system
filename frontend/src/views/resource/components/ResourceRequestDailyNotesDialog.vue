<template>
  <DraggableFormDialog
    ref="dialogRef"
    :model-value="modelValue"
    title="需求说明"
    width="min(560px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    class="resource-request-notes-dialog"
    :draggable="!pinned"
    non-modal
    :modal="false"
    modal-penetrable
    :lock-scroll="false"
    :close-on-press-escape="false"
    :z-index="windowZIndex"
    :close-on-click-modal="false"
    :before-close="beforeClose"
    @update:model-value="emit('update:modelValue', $event)"
    @open="handleOpen"
  >
    <template #header="{ titleId, titleClass }">
      <div class="daily-note-window-heading">
        <span :id="titleId" :class="titleClass">需求说明</span>
        <el-button size="small" :type="pinned ? 'primary' : 'default'" :aria-pressed="pinned" @mousedown.stop @click="togglePinned">
          {{ pinned ? '解除固定' : '固定' }}
        </el-button>
      </div>
    </template>
    <section v-if="canEdit" ref="editorSection" class="daily-note-editor">
      <div class="daily-note-editor__heading">
        <div>
          <h3>{{ existingNote ? '编辑当日说明' : '新增当日说明' }}</h3>
          <p>同一天保存为同一条说明，可切换日期补充或修改。</p>
        </div>
        <el-date-picker
          :model-value="editorDate"
          type="date"
          value-format="YYYY-MM-DD"
          format="YYYY年MM月DD日"
          :clearable="false"
          aria-label="需求说明日期"
          @update:model-value="switchDate"
        />
      </div>
      <RichTextComposer
        v-if="modelValue"
        :key="editorDate"
        v-model="draftContent"
        format-colors
        min-height="260px"
        placeholder="请输入当天的资源需求说明…"
      />
    </section>

    <el-alert
      v-else
      type="info"
      :closable="false"
      show-icon
      title="当前账号可查看需求说明，但没有编辑权限。"
    />

    <section class="daily-note-history" v-loading="loading">
      <div class="daily-note-history__heading">
        <div>
          <h3>历史说明</h3>
          <p>默认按说明日期从新到旧排列</p>
        </div>
        <el-button :loading="loading" @click="refreshNotes">刷新</el-button>
      </div>

      <el-empty v-if="!loading && !notes.length" description="暂无需求说明" :image-size="80" />
      <article v-for="note in notes" :key="note.id" class="daily-note-card">
        <header>
          <div>
            <strong>{{ formatNoteDate(note.noteDate) }}</strong>
            <span>由 {{ note.updatedByName || '未知用户' }} 更新于 {{ formatDateTime(note.updatedAt) }}</span>
          </div>
          <el-button
            v-if="canEdit"
            link
            type="primary"
            @click="editNote(note)"
          >编辑这一天</el-button>
        </header>
        <RichTextContent :document="note.contentJson" class="daily-note-card__content" />
      </article>
    </section>

    <template #footer>
      <div class="daily-note-footer">
        <span v-if="canEdit" class="daily-note-footer__hint">
          {{ existingNote ? `正在修改 ${formatNoteDate(editorDate)} 的说明` : `将新增 ${formatNoteDate(editorDate)} 的说明` }}
        </span>
        <span v-else></span>
        <div>
          <el-button :disabled="saving" @click="requestClose">关闭</el-button>
          <el-button v-if="canEdit" type="primary" :loading="saving" @click="saveNote">保存说明</el-button>
        </div>
      </div>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, useZIndex } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { getResourceRequestDailyNotes, saveResourceRequestDailyNote } from '@/api/resourceRequests'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { formatDateTimeMinute } from '@/utils/dateTime'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  canEdit: { type: Boolean, default: false },
  foregroundVersion: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue'])
const dialogRef = ref(null)
const pinned = ref(false)
const { nextZIndex } = useZIndex()
const windowZIndex = ref(nextZIndex())

function togglePinned() {
  pinned.value = !pinned.value
  if (pinned.value) windowZIndex.value = nextZIndex()
}

// 后方业务弹窗完成打开后再置顶，后续日期、颜色及确认浮层仍使用正常层级。
watch(() => props.foregroundVersion, async () => {
  await nextTick()
  if (props.modelValue && pinned.value) windowZIndex.value = nextZIndex()
})

function handleViewportResize() {
  if (props.modelValue) dialogRef.value?.resetPosition()
}
onMounted(() => window.addEventListener('resize', handleViewportResize))
onBeforeUnmount(() => window.removeEventListener('resize', handleViewportResize))

const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const cloneDocument = value => JSON.parse(JSON.stringify(value || emptyDocument()))
const localDate = (value = new Date()) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const loading = ref(false)
const saving = ref(false)
const notes = ref([])
const editorDate = ref(localDate())
const draftContent = ref(emptyDocument())
const originalContent = ref(JSON.stringify(emptyDocument()))
const editorSection = ref(null)

const existingNote = computed(() => notes.value.find(note => note.noteDate === editorDate.value) || null)
const isDirty = computed(() => props.canEdit && JSON.stringify(draftContent.value) !== originalContent.value)

function setEditorDate(value) {
  editorDate.value = value || localDate()
  draftContent.value = cloneDocument(existingNote.value?.contentJson)
  originalContent.value = JSON.stringify(draftContent.value)
}

async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前需求说明尚未保存，确定放弃修改吗？', '放弃修改', {
      type: 'warning',
      confirmButtonText: '放弃修改',
      cancelButtonText: '继续编辑',
    })
    return true
  } catch {
    return false
  }
}

async function switchDate(value) {
  if (!value || value === editorDate.value) return
  if (!await confirmDiscard()) return
  setEditorDate(value)
}

async function loadNotes() {
  if (loading.value) return
  loading.value = true
  try {
    const result = await getResourceRequestDailyNotes({ limit: 365 })
    notes.value = Array.isArray(result) ? result : []
    setEditorDate(editorDate.value || localDate())
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '需求说明加载失败'))
  } finally {
    loading.value = false
  }
}

async function handleOpen() {
  pinned.value = false
  windowZIndex.value = nextZIndex()
  setEditorDate(localDate())
  await loadNotes()
}

async function refreshNotes() {
  if (!await confirmDiscard()) return
  await loadNotes()
}

async function editNote(note) {
  if (!note?.noteDate || !await confirmDiscard()) return
  setEditorDate(note.noteDate)
  editorSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function containsText(node) {
  return Boolean(node?.text?.trim()) || (node?.content || []).some(containsText)
}

async function saveNote() {
  if (saving.value) return
  if (!containsText(draftContent.value)) {
    ElMessage.warning('请输入需求说明内容')
    return
  }
  saving.value = true
  try {
    const saved = await saveResourceRequestDailyNote(
      editorDate.value,
      draftContent.value,
      existingNote.value?.updatedAt,
    )
    const next = notes.value.filter(note => note.noteDate !== saved.noteDate)
    next.push(saved)
    notes.value = next.sort((left, right) => right.noteDate.localeCompare(left.noteDate))
    draftContent.value = cloneDocument(saved.contentJson)
    originalContent.value = JSON.stringify(draftContent.value)
    ElMessage.success('需求说明已保存')
  } catch (error) {
    const message = getLocalizedErrorMessage(error, '需求说明保存失败')
    ElMessage.error(error?.response?.status === 409 ? `${message}，请刷新后重试` : message)
  } finally {
    saving.value = false
  }
}

async function requestClose() {
  if (await confirmDiscard()) emit('update:modelValue', false)
}

async function beforeClose(done) {
  if (await confirmDiscard()) done()
}

function formatNoteDate(value) {
  const [year, month, day] = String(value || '').split('-')
  return year && month && day ? `${year}年${month}月${day}日` : '-'
}

const formatDateTime = value => formatDateTimeMinute(value) || '-'
</script>

<style scoped>
.daily-note-window-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.daily-note-editor { padding-bottom: 24px; border-bottom: 1px solid var(--el-border-color-lighter); }
.daily-note-editor__heading,.daily-note-history__heading,.daily-note-card header,.daily-note-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.daily-note-editor__heading,.daily-note-history__heading { margin-bottom: 14px; }
.daily-note-editor__heading h3,.daily-note-history__heading h3 { margin: 0; font-size: 16px; }
.daily-note-editor__heading p,.daily-note-history__heading p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.daily-note-history { padding-top: 24px; min-height: 180px; }
.daily-note-card { padding: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-bg-color); }
.daily-note-card + .daily-note-card { margin-top: 12px; }
.daily-note-card header > div { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
.daily-note-card header span { color: var(--el-text-color-secondary); font-size: 12px; }
.daily-note-card__content { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); }
.daily-note-footer { width: 100%; }
.daily-note-footer__hint { color: var(--el-text-color-secondary); font-size: 13px; }
:deep(.daily-note-card__content ul),:deep(.daily-note-card__content ol) { padding-left: 24px; }
@media (max-width: 640px) {
  .daily-note-editor__heading,.daily-note-card header,.daily-note-footer { align-items: flex-start; flex-direction: column; }
  .daily-note-editor__heading .el-date-editor { width: 100%; }
  .daily-note-card header > div { align-items: flex-start; flex-direction: column; gap: 4px; }
  .daily-note-footer > div { align-self: flex-end; }
}
</style>

<style>
.resource-request-notes-dialog { display: flex; flex-direction: column; max-height: 80vh; overflow: hidden; margin-right: 16px; margin-left: auto; }
.resource-request-notes-dialog .el-dialog__header,.resource-request-notes-dialog .el-dialog__footer { flex-shrink: 0; }
.resource-request-notes-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.resource-request-notes-dialog .el-dialog__footer { padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-lighter); }
</style>
