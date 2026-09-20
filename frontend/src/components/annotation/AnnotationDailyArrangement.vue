<template>
  <section
    ref="panelRef"
    class="daily-arrangement"
    :class="{ 'is-fallback-fullscreen': fallbackFullscreen }"
    v-loading="loading"
  >
    <header class="daily-arrangement__header">
      <div>
        <h3>今日安排</h3>
        <p>{{ formattedToday }} · 团队共享安排</p>
      </div>
      <div class="daily-arrangement__actions">
        <el-button :loading="loading" @click="loadNote">刷新</el-button>
        <el-button :icon="FullScreen" @click="toggleFullscreen">
          {{ fullscreenActive ? '退出全屏' : '全屏查看' }}
        </el-button>
        <el-button v-if="canEdit && !editing" type="primary" @click="startEditing">编辑内容</el-button>
      </div>
    </header>

    <div class="daily-arrangement__body">
      <template v-if="editing">
        <RichTextComposer
          v-model="draftContent"
          format-colors
          min-height="360px"
          placeholder="请输入今日项目安排、人员协调或需要团队注意的事项…"
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
          class="daily-arrangement__document"
        />
        <el-empty v-else-if="!loading" description="今日暂无安排" :image-size="96">
          <el-button v-if="canEdit" type="primary" @click="startEditing">填写今日安排</el-button>
        </el-empty>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { getArrangementDailyNote, saveArrangementDailyNote } from '@/api/annotationOps'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { formatDateTimeMinute } from '@/utils/dateTime'

defineProps({ canEdit: { type: Boolean, default: false } })

const BUSINESS_TIME_ZONE = 'Asia/Hong_Kong'
const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const cloneDocument = value => JSON.parse(JSON.stringify(value || emptyDocument()))

const panelRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const note = ref(null)
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
const formattedToday = computed(() => today.value.replace(/(\d{4})-(\d{2})-(\d{2})/, '$1年$2月$3日'))
const fullscreenActive = computed(() => nativeFullscreen.value || fallbackFullscreen.value)
const isDirty = computed(() => editing.value && JSON.stringify(draftContent.value) !== originalContent.value)

function hasContent(document) {
  const containsText = node => Boolean(node?.text?.trim()) || (node?.content || []).some(containsText)
  return Boolean(document && containsText(document))
}

async function loadNote() {
  if (loading.value) return
  if (isDirty.value && !await confirmDiscard()) return
  loading.value = true
  try {
    note.value = await getArrangementDailyNote(today.value)
    editing.value = false
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '今日安排加载失败'))
  } finally {
    loading.value = false
  }
}

function startEditing() {
  draftContent.value = cloneDocument(note.value?.contentJson)
  originalContent.value = JSON.stringify(draftContent.value)
  editing.value = true
}

async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '放弃修改', {
      type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑',
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
  if (saving.value) return
  if (!hasContent(draftContent.value)) {
    ElMessage.warning('请输入今日安排内容')
    return
  }
  saving.value = true
  try {
    note.value = await saveArrangementDailyNote(today.value, {
      contentJson: draftContent.value,
      expectedUpdatedAt: note.value?.updatedAt,
    })
    editing.value = false
    ElMessage.success('今日安排已保存')
  } catch (error) {
    const message = getLocalizedErrorMessage(error, '今日安排保存失败')
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
.daily-arrangement:fullscreen,.daily-arrangement.is-fallback-fullscreen { width: 100vw; height: 100vh; min-height: 100vh; padding: 24px 32px; background: var(--el-bg-color); }
.daily-arrangement.is-fallback-fullscreen { position: fixed; inset: 0; z-index: 3000; }
:deep(.daily-arrangement__document ul),:deep(.daily-arrangement__document ol) { padding-left: 24px; }
@media (max-width: 640px) {
  .daily-arrangement { padding: 16px; }
  .daily-arrangement__header { flex-direction: column; }
  .daily-arrangement__actions { width: 100%; justify-content: flex-start; }
  .daily-arrangement:fullscreen,.daily-arrangement.is-fallback-fullscreen { padding: 16px; }
}
</style>
