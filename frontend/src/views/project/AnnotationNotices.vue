<template>
  <el-card class="notice-page" shadow="never" v-loading="loading">
    <template #header>
      <div class="notice-page__header">
        <div>
          <h2>标注须知</h2>
          <p>集中查看和维护标注业务中的报价、试标及各类操作流程。</p>
        </div>
        <el-button @click="loadNotices">刷新</el-button>
      </div>
    </template>

    <el-select
      v-model="activeKey"
      class="notice-page__mobile-select"
      placeholder="请选择主题"
    >
      <el-option v-for="item in notices" :key="item.sectionKey" :label="item.title" :value="item.sectionKey" />
    </el-select>

    <div v-if="activeNotice" class="notice-layout">
      <nav class="notice-nav" aria-label="标注须知主题">
        <button
          v-for="item in notices"
          :key="item.sectionKey"
          type="button"
          :class="['notice-nav__item', { 'is-active': item.sectionKey === activeKey }]"
          @click="activeKey = item.sectionKey"
        >{{ item.title }}</button>
      </nav>

      <section class="notice-content">
        <div class="notice-content__heading">
          <div>
            <h3>{{ activeNotice.title }}</h3>
            <div class="notice-content__meta">
              <template v-if="activeNotice.updatedAt">
                最近由 {{ activeNotice.updatedByName || '未知用户' }} 编辑于 {{ formatDateTime(activeNotice.updatedAt) }}
              </template>
              <template v-else>尚未编辑</template>
            </div>
          </div>
          <el-button v-if="canEdit" type="primary" @click="openEditor">编辑内容</el-button>
        </div>

        <RichTextContent
          v-if="hasContent(activeNotice.contentJson)"
          :document="activeNotice.contentJson"
          class="notice-content__document"
        />
        <el-empty v-else description="暂无内容，等待补充" :image-size="96" />
      </section>
    </div>

    <el-empty v-else-if="!loading" description="标注须知加载失败，请刷新重试" />
  </el-card>

  <el-dialog
    v-model="editorVisible"
    :title="`编辑标注须知 · ${editingNotice?.title || ''}`"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    class="annotation-notice-dialog"
    :close-on-click-modal="false"
    :before-close="beforeEditorClose"
  >
    <RichTextComposer
      v-if="editorVisible"
      v-model="draftContent"
      format-colors
      min-height="360px"
      placeholder="请输入需要团队注意的事项…"
    />
    <template #footer>
      <el-button :disabled="saving" @click="requestEditorClose">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveNotice">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onActivated, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { getAnnotationNotices, updateAnnotationNotice } from '@/api/annotationNotices'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { hasPermission } from '@/utils/permission'

const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const notices = ref([])
const activeKey = ref('customer_quote')
const loading = ref(false)
const saving = ref(false)
const editorVisible = ref(false)
const editingNotice = ref(null)
const draftContent = ref(emptyDocument())
const originalContent = ref('')
let closingAfterSave = false

const canEdit = computed(() => hasPermission('projects:write'))
const activeNotice = computed(() => notices.value.find(item => item.sectionKey === activeKey.value) || notices.value[0])
const isDirty = computed(() => editorVisible.value && JSON.stringify(draftContent.value) !== originalContent.value)

const cloneDocument = value => JSON.parse(JSON.stringify(value || emptyDocument()))

function hasContent(document) {
  const containsText = node => Boolean(node?.text?.trim()) || (node?.content || []).some(containsText)
  return Boolean(document && containsText(document))
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }).format(date)
}

async function loadNotices() {
  loading.value = true
  try {
    const result = await getAnnotationNotices()
    notices.value = Array.isArray(result) ? result : []
    if (!notices.value.some(item => item.sectionKey === activeKey.value)) {
      activeKey.value = notices.value[0]?.sectionKey || 'customer_quote'
    }
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '标注须知加载失败'))
  } finally {
    loading.value = false
  }
}

function openEditor() {
  if (!activeNotice.value) return
  editingNotice.value = activeNotice.value
  draftContent.value = cloneDocument(activeNotice.value.contentJson)
  originalContent.value = JSON.stringify(draftContent.value)
  editorVisible.value = true
}

async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '放弃修改', {
      type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑'
    })
    return true
  } catch {
    return false
  }
}

async function requestEditorClose() {
  if (await confirmDiscard()) editorVisible.value = false
}

async function beforeEditorClose(done) {
  if (closingAfterSave || await confirmDiscard()) done()
}

async function saveNotice() {
  if (!editingNotice.value || saving.value) return
  saving.value = true
  try {
    const saved = await updateAnnotationNotice(
      editingNotice.value.sectionKey,
      draftContent.value,
      editingNotice.value.updatedAt
    )
    const index = notices.value.findIndex(item => item.sectionKey === saved.sectionKey)
    if (index >= 0) notices.value.splice(index, 1, saved)
    closingAfterSave = true
    editorVisible.value = false
    ElMessage.success('标注须知已保存')
  } catch (error) {
    const conflict = error?.response?.status === 409
    ElMessage.error(conflict
      ? '该主题已被他人更新，请取消编辑并刷新后重试'
      : getLocalizedErrorMessage(error, '标注须知保存失败'))
  } finally {
    saving.value = false
    closingAfterSave = false
  }
}

onActivated(() => {
  if (!editorVisible.value) loadNotices()
})
</script>

<style scoped>
.notice-page__header{display:flex;align-items:center;justify-content:space-between;gap:16px}.notice-page__header h2{margin:0;font-size:20px}.notice-page__header p{margin:6px 0 0;color:var(--el-text-color-secondary);font-size:13px}.notice-layout{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:520px;border:1px solid var(--el-border-color-lighter);border-radius:8px;overflow:hidden}.notice-nav{padding:10px;background:var(--el-fill-color-lighter);border-right:1px solid var(--el-border-color-lighter)}.notice-nav__item{display:block;width:100%;padding:11px 12px;border:0;border-radius:6px;background:transparent;color:var(--el-text-color-regular);font:inherit;text-align:left;cursor:pointer}.notice-nav__item:hover{background:var(--el-fill-color)}.notice-nav__item.is-active{background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:600}.notice-content{min-width:0;padding:24px}.notice-content__heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding-bottom:18px;border-bottom:1px solid var(--el-border-color-lighter)}.notice-content__heading h3{margin:0;font-size:20px}.notice-content__meta{margin-top:7px;color:var(--el-text-color-secondary);font-size:13px}.notice-content__document{padding:22px 4px;min-height:300px}.notice-page__mobile-select{display:none;width:100%;margin-bottom:14px}:deep(.notice-content__document ul),:deep(.notice-content__document ol){padding-left:24px}:deep(.notice-content__document h1),:deep(.notice-content__document h2),:deep(.notice-content__document h3){margin:14px 0 8px}:deep(.notice-content__document blockquote){margin:12px 0;padding-left:14px;border-left:3px solid var(--el-border-color);color:var(--el-text-color-secondary)}
@media (max-width:768px){.notice-page__mobile-select{display:block}.notice-layout{display:block;min-height:420px}.notice-nav{display:none}.notice-content{padding:18px}.notice-content__heading{align-items:center}.notice-page__header p{display:none}}
</style>

<style>
.annotation-notice-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.annotation-notice-dialog .el-dialog__header,.annotation-notice-dialog .el-dialog__footer{flex-shrink:0}.annotation-notice-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-notice-dialog .el-dialog__footer{padding-top:14px;border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
</style>
