<template>
  <AnnotationOfficeEditor v-if="isOffice" :key="request.serial" />
  <DraggableFormDialog v-else
    :model-value="state.open"
    width="min(1200px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    destroy-on-close
    class="material-editor-dialog"
    :close-on-click-modal="false"
    :before-close="beforeClose"
    @update:model-value="value => { if (!value) closeMaterialEditor() }"
  >
    <template #header>
      <div class="material-editor-title">
        <span class="material-editor-title__label">{{ creating ? '新建' : '在线编辑' }}</span>
        <span class="material-editor-title__name" @mousedown.stop>{{ fileName }}</span>
        <el-tag v-if="baseVersion" size="small" type="info">基于 V{{ baseVersion.version_no }}</el-tag>
      </div>
    </template>

    <div v-loading="loading" class="material-editor-body" element-loading-text="正在打开文件…">
      <el-result v-if="loadError" icon="error" :title="loadError">
        <template #extra><el-button type="primary" @click="load">重新加载</el-button></template>
      </el-result>
      <template v-else-if="!loading">
        <AppForm v-if="creating" ref="nameFormRef" :model="nameForm" :rules="nameRules" label-width="80px" class="material-editor-name" @submit.prevent>
          <el-form-item label="文件名称" prop="name">
            <el-input v-model="nameForm.name" maxlength="250" placeholder="请输入文件名称，扩展名自动补充" :disabled="saving"><template #append>{{ ONLINE_EDIT_KINDS[kind].extension }}</template></el-input>
          </el-form-item>
          <small class="material-editor-name__hint">保存到“{{ request.create.folderName }}”，保存后立即生效，无需保存项目。</small>
        </AppForm>
        <el-alert v-if="encodingNotice" type="info" :closable="false" show-icon :title="encodingNotice" />

        <div class="material-text" :class="{ 'material-text--split': kind === 'markdown' }">
          <textarea v-model="text" class="material-text__source" :readonly="saving" spellcheck="false"
            :aria-label="`${fileName} 内容`" :placeholder="kind === 'markdown' ? '使用 Markdown 语法编写，右侧实时预览' : '请输入文本内容'" />
          <!-- markdown-it 关闭 html 选项，原始 HTML 会被转义，预览不执行脚本。 -->
          <div v-if="kind === 'markdown'" class="material-text__preview" aria-label="Markdown 预览" v-html="preview" />
        </div>
      </template>
    </div>

    <template #footer>
      <span class="material-editor-status">{{ dirty ? '有未保存的修改' : (creating ? '保存后在当前目录生成文件' : '保存后生成新版本，历史版本保留') }}</span>
      <el-button :disabled="saving" @click="requestClose">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading || !!loadError" @click="save">{{ creating ? '保存文件' : '保存为新版本' }}</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownIt from 'markdown-it'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import * as api from '@/api/annotationMaterials'
import { useMaterialEditor } from '@/composables/useMaterialEditor'
import { ONLINE_EDIT_KINDS, decodeText, documentFileName, documentNameError, encodeText, onlineEditKind, textMime } from '@/utils/materialDocument'
const AnnotationOfficeEditor = defineAsyncComponent(() => import('./AnnotationOfficeEditor.vue'))

const { state, closeMaterialEditor, notifyMaterialSaved } = useMaterialEditor()
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
// 预览中的链接在新窗口打开，避免离开系统导致未保存内容丢失。
markdown.renderer.rules.link_open = (tokens, index, options, _env, self) => {
  tokens[index].attrSet('target', '_blank'); tokens[index].attrSet('rel', 'noopener noreferrer')
  return self.renderToken(tokens, index, options)
}

const loading = ref(false), loadError = ref(''), saving = ref(false)
const kind = ref(null), text = ref(''), originalText = ref('')
const textFormat = ref({ eol: '\n', bom: false, encoding: 'utf-8' })
const request = computed(() => state.request)
const isOffice = computed(() => (request.value?.create?.kind || onlineEditKind(request.value?.file?.original_name)) === 'docx')
const creating = computed(() => Boolean(request.value?.create))
const baseVersion = computed(() => request.value?.file || null)
const nameFormRef = ref(null), nameForm = reactive({ name: '' })
const nameRules = { name: [{ validator: (_rule, value, callback) => {
  const error = documentNameError(value, kind.value, request.value?.create?.siblingNames || [])
  callback(error ? new Error(error) : undefined)
}, trigger: 'blur' }] }
const fileName = computed(() => {
  if (!creating.value) return request.value?.file?.original_name || ''
  return nameForm.name.trim() ? documentFileName(nameForm.name, kind.value) : `未命名${ONLINE_EDIT_KINDS[kind.value]?.extension || ''}`
})
const dirty = computed(() => (creating.value && Boolean(nameForm.name.trim())) || text.value !== originalText.value)
const preview = computed(() => kind.value === 'markdown' ? markdown.render(text.value) : '')
const encodingNotice = computed(() => ({
  gb18030: '原文件为 GBK/GB18030 编码，保存后将转换为 UTF-8 编码。',
  'utf-16le': '原文件为 UTF-16 编码，保存后将转换为 UTF-8 编码。',
  'utf-16be': '原文件为 UTF-16 编码，保存后将转换为 UTF-8 编码。',
})[textFormat.value.encoding] || '')

let loadSerial = 0
async function load() {
  const current = request.value
  const serial = ++loadSerial
  if (!current) return
  loading.value = true; loadError.value = ''
  kind.value = current.create?.kind || onlineEditKind(current.file?.original_name)
  try {
      let decoded = { text: '', eol: '\n', bom: false, encoding: 'utf-8' }
      if (!current.create) decoded = decodeText(await (await api.readMaterialVersion(current.projectId, current.file)).arrayBuffer())
      if (serial !== loadSerial) return
      textFormat.value = decoded; text.value = decoded.text; originalText.value = decoded.text
  } catch (error) {
    if (serial === loadSerial) loadError.value = error.detail || '文件无法打开，可能已损坏或不是有效的文档'
  } finally {
    if (serial === loadSerial) loading.value = false
  }
}

async function buildFile() {
  const { eol, bom, encoding } = textFormat.value
  return new File([encodeText(text.value, { eol, bom: bom && encoding === 'utf-8' })], fileName.value, { type: textMime(kind.value) })
}

async function save() {
  const current = request.value
  if (saving.value || loading.value || loadError.value || !current) return
  if (current.create && !(await nameFormRef.value?.validate().catch(() => false))) return
  if (request.value !== current) return
  saving.value = true
  let upload = null
  try {
    const file = await buildFile()
    if (!file.size) { ElMessage.warning('文件内容不能为空'); return }
    upload = await api.uploadMaterial(file)
    if (current.create) await api.createOnlineFile(current.projectId, { upload_id: upload.id, folder_id: current.create.folderId || null })
    else await api.commitOnlineVersion(current.projectId, current.file.file_id, { upload_id: upload.id, base_version_id: current.file.id })
    upload = null
    notifyMaterialSaved(current.projectId)
    ElMessage.success(current.create ? '文件已保存' : '已保存为新版本')
    originalText.value = text.value
    closeMaterialEditor()
  } catch (error) {
    // 冲突时保留编辑内容，便于用户复制后刷新重新编辑。
    const message = error.response?.status === 409 ? '文件已被他人更新，请复制当前内容后关闭并重新打开最新版本' : (error.detail || '保存失败，请重试')
    ElMessage.error({ message, duration: 6000 })
  } finally {
    if (upload) void api.cancelMaterialUpload(upload.id).catch(() => { /* 暂存由云端24小时过期清理兜底。 */ })
    saving.value = false
  }
}

async function confirmDiscard() {
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，关闭后将丢失。是否放弃修改？', '放弃修改', { type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', appendTo: document.body })
    return true
  } catch { return false }
}
async function beforeClose(done) { if (!saving.value && await confirmDiscard()) done() }
async function requestClose() { if (!saving.value && await confirmDiscard()) closeMaterialEditor() }

function teardown() {
  loadSerial += 1
  text.value = ''; originalText.value = ''; nameForm.name = ''; loadError.value = ''; kind.value = null
}
watch(() => request.value?.serial, value => { teardown(); if (value && !isOffice.value) void load() }, { immediate: true })
onBeforeUnmount(teardown)
</script>

<style scoped>
.material-editor-title { display: flex; align-items: center; gap: 8px; min-width: 0; padding-right: 32px; }
.material-editor-title__label { font-size: 16px; font-weight: 600; flex-shrink: 0; }
.material-editor-title__name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; user-select: text; cursor: text; }
.material-editor-body { display: flex; flex-direction: column; gap: 8px; min-height: 60vh; height: 100%; }
.material-text { flex: 1; min-height: 0; display: grid; gap: 12px; }
.material-text--split { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.material-text__source { width: 100%; min-height: 60vh; resize: none; box-sizing: border-box; padding: 12px; border: 1px solid var(--el-border-color); border-radius: 8px; background: #fff; font: 13px/1.7 Consolas, 'Courier New', monospace; color: var(--el-text-color-primary); }
.material-text__source:focus { outline: none; border-color: var(--el-color-primary); }
.material-text__preview { min-height: 60vh; padding: 12px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-fill-color-blank); overflow-wrap: anywhere; line-height: 1.75; }
.material-text__preview :deep(pre) { padding: 8px; background: var(--el-fill-color-light); overflow-x: auto; }
.material-text__preview :deep(table) { border-collapse: collapse; }
.material-text__preview :deep(td), .material-text__preview :deep(th) { border: 1px solid var(--el-border-color); padding: 4px 8px; }
.material-text__preview :deep(img) { max-width: 100%; }
.material-editor-name { flex-shrink: 0; }
.material-editor-name :deep(.el-form-item) { margin-bottom: 4px; }
.material-editor-name__hint { display: block; padding-left: 80px; color: var(--el-text-color-secondary); font-size: 12px; }
.material-editor-status { margin-right: auto; color: var(--el-text-color-secondary); font-size: 12px; }
@media (max-width: 768px) {
  .material-text--split { grid-template-columns: minmax(0, 1fr); }
  .material-text__source, .material-text__preview { min-height: 40vh; }
}
</style>

<style>
.el-dialog.material-editor-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.material-editor-dialog .el-dialog__header,.material-editor-dialog .el-dialog__footer { flex-shrink: 0; }
.material-editor-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.material-editor-dialog .el-dialog__footer { display: flex; align-items: center; gap: 8px; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); }
</style>
