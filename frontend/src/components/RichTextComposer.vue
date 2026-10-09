<template>
  <div class="rich-editor">
    <fieldset v-if="editor" class="rich-editor__toolbar" :disabled="imageUploading || disabled">
      <el-button-group>
        <el-button size="small" :type="editor.isActive('bold') ? 'primary' : ''" @click="editor.chain().focus().toggleBold().run()">加粗</el-button>
        <el-button size="small" :type="editor.isActive('italic') ? 'primary' : ''" @click="editor.chain().focus().toggleItalic().run()">斜体</el-button>
        <el-button size="small" :type="editor.isActive('strike') ? 'primary' : ''" @click="editor.chain().focus().toggleStrike().run()">删除线</el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" :type="editor.isActive('heading', { level: 2 }) ? 'primary' : ''" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()">标题</el-button>
        <el-button size="small" :type="editor.isActive('bulletList') ? 'primary' : ''" @click="editor.chain().focus().toggleBulletList().run()">项目符号</el-button>
        <el-button size="small" :type="editor.isActive('orderedList') ? 'primary' : ''" @click="editor.chain().focus().toggleOrderedList().run()">编号</el-button>
        <el-button size="small" :type="editor.isActive('blockquote') ? 'primary' : ''" @click="editor.chain().focus().toggleBlockquote().run()">引用</el-button>
      </el-button-group>
      <template v-if="formatColors">
        <span class="rich-editor__color-label">字体颜色</span>
        <el-color-picker
          v-model="selectedColor"
          color-format="hex"
          size="small"
          :predefine="predefinedColors"
          @change="applyTextColor"
        />
        <el-button
          size="small"
          :type="editor.isActive('highlight') ? 'warning' : ''"
          @click="editor.chain().focus().toggleMark('highlight', { color: '#fff59d' }).run()"
        >黄色高亮</el-button>
        <el-tooltip content="字体颜色或高亮异常时，请全选内容并清除格式后重新设置" placement="top">
          <el-button size="small" @click="clearFormatting">清除格式</el-button>
        </el-tooltip>
      </template>
      <el-button size="small" @click="editor.chain().focus().undo().run()">撤销</el-button>
      <el-button size="small" @click="editor.chain().focus().redo().run()">重做</el-button>
      <span v-if="imageApi" class="rich-editor__color-label" role="status">{{ imageUploading ? '图片上传中，请稍候…' : '支持粘贴截图及图片（PNG、JPEG、WebP，单张最多20MB）' }}</span>
    </fieldset>
    <EditorContent :editor="editor" class="rich-editor__content" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { TextColor, YellowHighlight } from '@/utils/richTextMarks'
import { pasteWithoutFormatting } from '@/utils/plainTextPaste'
import { handleWebLinkClick, linkifyDocument, noticeLinkOptions } from '@/utils/richTextLinks'
import { clipboardImageTokens, createAuthenticatedImage, imageFileKey, imagePasteSlice, pasteImageFile } from '@/utils/richTextImages'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import '@/styles/rich-text-images.css'

const props = defineProps({
  modelValue: { type: Object, default: null },
  placeholder: { type: String, default: '请输入留言内容…' },
  formatColors: Boolean,
  plainTextPaste: Boolean,
  enableLinks: Boolean,
  imageApi: { type: Object, default: null },
  imageSectionId: { type: String, default: '' },
  disabled: Boolean,
  minHeight: { type: String, default: '132px' }
})

const emit = defineEmits(['update:modelValue', 'update:plainText', 'uploading-change'])

const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const minHeight = computed(() => props.minHeight)
const selectedColor = ref('#1f2937')
const predefinedColors = ['#1f2937', '#475569', '#2563eb', '#0f766e', '#b45309', '#b91c1c', '#7e22ce']
const imageUploading = ref(false)
const uploadedImages = new Map()
let pasteController
let disposed = false
let pasteSequence = 0

function setUploading(value) {
  imageUploading.value = value
  editor.value?.setEditable(!value && !props.disabled)
  emit('uploading-change', value)
}

async function removeDraft(id) {
  const entry = uploadedImages.get(id)
  if (!entry) return
  uploadedImages.delete(id)
  try { await props.imageApi.removeDraft(entry.sectionId, id) } catch { /* 中断或失联的草稿由服务端24小时清理兜底。 */ }
}

function cleanupDraftImages() {
  pasteSequence++
  pasteController?.abort()
  return Promise.all([...uploadedImages.keys()].map(removeDraft))
}

function markImagesSaved(document) {
  const usedSources = new Set()
  const visit = node => {
    if (node?.type === 'image') usedSources.add(node.attrs?.src)
    ;(node?.content || []).forEach(visit)
  }
  visit(document)
  for (const [id, entry] of uploadedImages) {
    if (usedSources.has(entry.src)) uploadedImages.delete(id)
  }
  return cleanupDraftImages()
}

function handleImagePaste(view, event) {
  if (!props.imageApi) return false
  if (imageUploading.value || props.disabled) { event.preventDefault(); return true }
  const tokens = clipboardImageTokens(event.clipboardData)
  if (!tokens) return false
  event.preventDefault()
  const selection = view.state.selection
  const sectionId = props.imageSectionId
  const current = ++pasteSequence
  pasteController = new AbortController()
  const controller = pasteController
  setUploading(true)
  ;(async () => {
    const savedByHash = new Map()
    try {
      for (const token of tokens) {
        if (!token.image) continue
        if (disposed || current !== pasteSequence) return
        let timer
        try {
          timer = setTimeout(() => controller.abort(), 120000)
          const file = await pasteImageFile(token.image, controller.signal, props.imageApi.read)
          const hash = await imageFileKey(file)
          if (disposed || current !== pasteSequence) return
          let saved = savedByHash.get(hash)
          if (saved && token.image.supplemental) continue
          if (!saved) {
            saved = await props.imageApi.upload(sectionId, file, controller.signal)
            uploadedImages.set(saved.id, { sectionId, src: saved.src })
            if (disposed || current !== pasteSequence) { await removeDraft(saved.id); return }
            savedByHash.set(hash, saved)
          }
          token.saved = saved
        } catch (error) {
          if (disposed || current !== pasteSequence) return
          if (controller.signal.aborted) { ElMessage.error('图片上传超时，请重新粘贴'); break }
          ElMessage.error(getLocalizedErrorMessage(error, '无法读取或上传图片，请重新截图粘贴'))
        } finally { clearTimeout(timer) }
      }
      if (disposed || current !== pasteSequence) return
      const slice = imagePasteSlice(view.state.schema, tokens)
      if (slice.content.size) view.dispatch(view.state.tr.setSelection(selection).replaceSelection(slice).scrollIntoView())
    } catch (error) {
      if (!disposed && current === pasteSequence) ElMessage.error(getLocalizedErrorMessage(error, '图文粘贴失败，请重新粘贴'))
    } finally {
      if (!disposed && current === pasteSequence) { setUploading(false); view.focus() }
    }
  })()
  return true
}

const editor = useEditor({
  content: (props.enableLinks ? linkifyDocument(props.modelValue) : props.modelValue) || emptyDocument(),
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      link: props.enableLinks ? noticeLinkOptions : false
    }),
    TextColor,
    YellowHighlight,
    ...(props.imageApi ? [createAuthenticatedImage(props.imageApi.read)] : [])
  ],
  editorProps: {
    handleDOMEvents: { paste: handleImagePaste },
    handleDrop: () => Boolean(props.imageApi),
    handleClick: (view, pos, event) => props.enableLinks ? handleWebLinkClick(view, pos, event) : false,
    handlePaste: (view, event, slice) => props.plainTextPaste
      ? pasteWithoutFormatting(view, event, slice)
      : false,
    attributes: {
      class: 'rich-editor__prose',
      'data-placeholder': props.placeholder
    }
  },
  onUpdate: ({ editor: currentEditor }) => {
    emit('update:modelValue', currentEditor.getJSON())
    emit('update:plainText', currentEditor.getText({ blockSeparator: '\n' }).trim())
  },
  onSelectionUpdate: ({ editor: currentEditor }) => {
    selectedColor.value = currentEditor.getAttributes('textColor').color || '#1f2937'
  }
})

const applyTextColor = (color) => {
  if (imageUploading.value || props.disabled) return
  if (color) editor.value?.chain().focus().setMark('textColor', { color }).run()
}

const clearFormatting = () => {
  editor.value?.chain().focus().unsetAllMarks().run()
  selectedColor.value = '#1f2937'
}

watch(
  () => props.modelValue,
  (value) => {
    if (!editor.value || !value) return
    if (JSON.stringify(editor.value.getJSON()) !== JSON.stringify(value)) {
      editor.value.commands.setContent(props.enableLinks ? linkifyDocument(value) : value, { emitUpdate: false })
    }
  }
)

defineExpose({
  cleanupDraftImages,
  markImagesSaved,
  clear: () => editor.value?.commands.setContent(emptyDocument(), false),
  focus: () => editor.value?.commands.focus()
})

watch(() => props.disabled, value => editor.value?.setEditable(!value && !imageUploading.value))
onBeforeUnmount(() => { disposed = true; cleanupDraftImages() })
</script>

<style scoped>
.rich-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  overflow: hidden;
}

.rich-editor__toolbar {
  margin: 0;
  min-width: 0;
  border: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}

.rich-editor__content {
  min-height: v-bind(minHeight);
}

:deep(.rich-editor__prose) {
  min-height: calc(v-bind(minHeight) - 24px);
  padding: 12px;
  outline: none;
  line-height: 1.7;
  color: var(--el-text-color-primary);
}

.rich-editor__color-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

:deep(.rich-editor__prose p:first-child:last-child:empty::before) {
  content: attr(data-placeholder);
  color: var(--el-text-color-placeholder);
  pointer-events: none;
}

:deep(.rich-editor__prose p) {
  margin: 0 0 8px;
}

:deep(.rich-editor__prose a) {
  color: var(--el-color-primary);
  text-decoration: underline;
  cursor: pointer;
}

:deep(.rich-editor__prose ul),
:deep(.rich-editor__prose ol) {
  margin: 0 0 8px;
  padding-left: 28px;
}

:deep(.rich-editor__prose li > p) {
  margin-bottom: 0;
}

:deep(.rich-editor__prose h1),
:deep(.rich-editor__prose h2),
:deep(.rich-editor__prose h3) {
  margin: 4px 0 10px;
}
</style>
