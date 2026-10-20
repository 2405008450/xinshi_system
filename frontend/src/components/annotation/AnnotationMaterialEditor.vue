<template>
  <DraggableFormDialog
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
        <el-alert v-if="kind === 'docx'" type="warning" :closable="false" show-icon
          title="在线编辑仅保留标题、段落、列表、表格、图片和常用文字格式；页眉页脚、批注、修订及复杂样式会丢失，原文件保留在历史版本中。" />
        <el-alert v-else-if="encodingNotice" type="info" :closable="false" show-icon :title="encodingNotice" />
        <el-alert v-for="warning in warnings" :key="warning" type="info" :closable="false" :title="warning" />

        <div v-if="kind === 'docx'" class="material-docx">
          <fieldset v-if="editor" class="material-docx__toolbar" :disabled="saving">
            <el-button-group>
              <el-button v-for="item in markButtons" :key="item.name" size="small" :type="editor.isActive(item.name) ? 'primary' : ''" @click="item.run()">{{ item.label }}</el-button>
            </el-button-group>
            <el-button-group>
              <el-button v-for="level in [1, 2, 3]" :key="level" size="small" :type="editor.isActive('heading', { level }) ? 'primary' : ''" @click="chain().toggleHeading({ level }).run()">标题{{ level }}</el-button>
            </el-button-group>
            <el-button-group>
              <el-button size="small" :type="editor.isActive('bulletList') ? 'primary' : ''" @click="chain().toggleBulletList().run()">项目符号</el-button>
              <el-button size="small" :type="editor.isActive('orderedList') ? 'primary' : ''" @click="chain().toggleOrderedList().run()">编号</el-button>
              <el-button size="small" :type="editor.isActive('blockquote') ? 'primary' : ''" @click="chain().toggleBlockquote().run()">引用</el-button>
            </el-button-group>
            <el-dropdown trigger="click" @command="tableCommand">
              <el-button size="small">表格</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="insert">插入 3×3 表格</el-dropdown-item>
                  <el-dropdown-item command="addRowAfter" :disabled="!inTable" divided>下方插入行</el-dropdown-item>
                  <el-dropdown-item command="addColumnAfter" :disabled="!inTable">右侧插入列</el-dropdown-item>
                  <el-dropdown-item command="deleteRow" :disabled="!inTable" divided>删除当前行</el-dropdown-item>
                  <el-dropdown-item command="deleteColumn" :disabled="!inTable">删除当前列</el-dropdown-item>
                  <el-dropdown-item command="deleteTable" :disabled="!inTable">删除表格</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button size="small" @click="chain().unsetAllMarks().clearNodes().run()">清除格式</el-button>
            <el-button size="small" @click="chain().undo().run()">撤销</el-button>
            <el-button size="small" @click="chain().redo().run()">重做</el-button>
          </fieldset>
          <EditorContent v-if="editor" :editor="editor" class="material-docx__content" />
        </div>

        <div v-else class="material-text" :class="{ 'material-text--split': kind === 'markdown' }">
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
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Editor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { TableKit } from '@tiptap/extension-table'
import MarkdownIt from 'markdown-it'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import * as api from '@/api/annotationMaterials'
import { useMaterialEditor } from '@/composables/useMaterialEditor'
import { DOCX_MIME, ONLINE_EDIT_KINDS, decodeText, documentFileName, documentNameError, encodeText, onlineEditKind, textMime } from '@/utils/materialDocument'
// mammoth 与 docx 体积较大，仅在打开或保存 Word 文档时加载。
const loadDocx = () => import('@/utils/materialDocx')

const { state, closeMaterialEditor, notifyMaterialSaved } = useMaterialEditor()
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
// 预览中的链接在新窗口打开，避免离开系统导致未保存内容丢失。
markdown.renderer.rules.link_open = (tokens, index, options, _env, self) => {
  tokens[index].attrSet('target', '_blank'); tokens[index].attrSet('rel', 'noopener noreferrer')
  return self.renderToken(tokens, index, options)
}
const MAX_PASTED_IMAGE = 5 * 1024 * 1024

const loading = ref(false), loadError = ref(''), saving = ref(false), warnings = ref([])
const kind = ref(null), text = ref(''), originalText = ref(''), docxDirty = ref(false), inTable = ref(false)
const textFormat = ref({ eol: '\n', bom: false, encoding: 'utf-8' })
const editor = shallowRef(null)
const request = computed(() => state.request)
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
const dirty = computed(() => (creating.value && Boolean(nameForm.name.trim())) || (kind.value === 'docx' ? docxDirty.value : text.value !== originalText.value))
const preview = computed(() => kind.value === 'markdown' ? markdown.render(text.value) : '')
const encodingNotice = computed(() => ({
  gb18030: '原文件为 GBK/GB18030 编码，保存后将转换为 UTF-8 编码。',
  'utf-16le': '原文件为 UTF-16 编码，保存后将转换为 UTF-8 编码。',
  'utf-16be': '原文件为 UTF-16 编码，保存后将转换为 UTF-8 编码。',
})[textFormat.value.encoding] || '')

const chain = () => editor.value.chain().focus()
const markButtons = [
  { name: 'bold', label: '加粗', run: () => chain().toggleBold().run() },
  { name: 'italic', label: '斜体', run: () => chain().toggleItalic().run() },
  { name: 'underline', label: '下划线', run: () => chain().toggleUnderline().run() },
  { name: 'strike', label: '删除线', run: () => chain().toggleStrike().run() },
]
function tableCommand(command) {
  if (command === 'insert') chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
  else chain()[command]().run()
}

// 只接受内嵌图片，避免文档中的外链图片在打开时向第三方发起请求。
const InlineImage = Image.extend({ parseHTML: () => [{ tag: 'img[src^="data:image/"]' }] }).configure({ allowBase64: true })

function pasteImage(view, event) {
  const file = [...(event.clipboardData?.files || [])].find(item => /^image\/(png|jpeg|gif)$/.test(item.type))
  if (!file) return false
  event.preventDefault()
  if (file.size > MAX_PASTED_IMAGE) { ElMessage.warning('粘贴的图片不能超过5MB'); return true }
  const reader = new FileReader()
  reader.onload = () => editor.value?.chain().focus().setImage({ src: reader.result }).run()
  reader.readAsDataURL(file)
  return true
}

function createEditor(html) {
  editor.value?.destroy()
  editor.value = new Editor({
    content: html || '<p></p>',
    extensions: [StarterKit.configure({ link: { openOnClick: false, autolink: true } }), InlineImage, TableKit.configure({ table: { resizable: false } })],
    editorProps: { attributes: { class: 'material-docx__prose' }, handlePaste: pasteImage },
    onUpdate: () => { docxDirty.value = true },
    onSelectionUpdate: ({ editor: current }) => { inTable.value = current.isActive('table') },
  })
}

let loadSerial = 0
async function load() {
  const current = request.value
  const serial = ++loadSerial
  if (!current) return
  loading.value = true; loadError.value = ''; warnings.value = []; docxDirty.value = false
  kind.value = current.create?.kind || onlineEditKind(current.file?.original_name)
  try {
    if (kind.value === 'docx') {
      let html = ''
      if (!current.create) {
        const blob = await api.readMaterialVersion(current.projectId, current.file)
        const { docxToHtml } = await loadDocx()
        const result = await docxToHtml(await blob.arrayBuffer())
        html = result.html; warnings.value = result.warnings.length ? [`有 ${result.warnings.length} 处格式无法识别，已按普通文本处理。`] : []
      }
      if (serial !== loadSerial) return
      createEditor(html)
    } else {
      let decoded = { text: '', eol: '\n', bom: false, encoding: 'utf-8' }
      if (!current.create) decoded = decodeText(await (await api.readMaterialVersion(current.projectId, current.file)).arrayBuffer())
      if (serial !== loadSerial) return
      textFormat.value = decoded; text.value = decoded.text; originalText.value = decoded.text
    }
  } catch (error) {
    if (serial === loadSerial) loadError.value = error.detail || '文件无法打开，可能已损坏或不是有效的文档'
  } finally {
    if (serial === loadSerial) loading.value = false
  }
}

async function buildFile() {
  if (kind.value === 'docx') {
    const { tiptapJsonToDocx } = await loadDocx()
    return new File([await tiptapJsonToDocx(editor.value.getJSON())], fileName.value, { type: DOCX_MIME })
  }
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
    docxDirty.value = false; originalText.value = text.value
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
  editor.value?.destroy(); editor.value = null
  text.value = ''; originalText.value = ''; docxDirty.value = false; nameForm.name = ''; loadError.value = ''; warnings.value = []; kind.value = null
}
watch(() => request.value?.serial, value => { teardown(); if (value) void load() }, { immediate: true })
onBeforeUnmount(teardown)
</script>

<style scoped>
.material-editor-title { display: flex; align-items: center; gap: 8px; min-width: 0; padding-right: 32px; }
.material-editor-title__label { font-size: 16px; font-weight: 600; flex-shrink: 0; }
.material-editor-title__name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; user-select: text; cursor: text; }
.material-editor-body { display: flex; flex-direction: column; gap: 8px; min-height: 60vh; height: 100%; }
.material-docx { flex: 1; min-height: 0; display: flex; flex-direction: column; border: 1px solid var(--el-border-color); border-radius: 8px; background: #fff; }
.material-docx__toolbar { margin: 0; border: 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 8px; border-bottom: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); position: sticky; top: 0; z-index: 1; border-radius: 8px 8px 0 0; }
.material-docx__content { flex: 1; }
:deep(.material-docx__prose) { min-height: 50vh; padding: 16px 24px; outline: none; line-height: 1.75; color: var(--el-text-color-primary); overflow-wrap: anywhere; }
:deep(.material-docx__prose img) { max-width: 100%; height: auto; }
:deep(.material-docx__prose blockquote) { margin: 8px 0; padding-left: 12px; border-left: 3px solid var(--el-border-color); color: var(--el-text-color-regular); }
:deep(.material-docx__prose table) { border-collapse: collapse; width: 100%; margin: 8px 0; table-layout: fixed; }
:deep(.material-docx__prose td), :deep(.material-docx__prose th) { border: 1px solid var(--el-border-color); padding: 6px 8px; vertical-align: top; }
:deep(.material-docx__prose th) { background: #F1F5F9; font-weight: 600; }
:deep(.material-docx__prose .selectedCell) { background: var(--el-color-primary-light-9); }
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
  :deep(.material-docx__prose) { padding: 12px; }
}
</style>

<style>
.el-dialog.material-editor-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.material-editor-dialog .el-dialog__header,.material-editor-dialog .el-dialog__footer { flex-shrink: 0; }
.material-editor-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.material-editor-dialog .el-dialog__footer { display: flex; align-items: center; gap: 8px; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); }
</style>
