<template>
  <div
    class="mail-body-editor"
    :class="{ 'is-dragging': dragging, 'is-readonly': readonly }"
    @dragenter.prevent="dragging = true"
    @dragover.prevent
    @dragleave.self="dragging = false"
    @drop.prevent="handleDrop"
  >
    <div v-if="!readonly" class="mail-body-editor__toolbar">
      <el-upload
        :show-file-list="false"
        :http-request="({ file }) => addFile(file)"
        accept="image/jpeg,image/png,image/webp"
        multiple
        :disabled="uploading || images.length >= MAX_IMAGE_COUNT"
      >
        <el-button size="small" :loading="uploading">插入图片</el-button>
      </el-upload>
      <span>支持选择、粘贴或拖拽；单张 2MB，最多 5 张，合计 8MB</span>
      <strong>{{ images.length }}/{{ MAX_IMAGE_COUNT }} · {{ formattedTotalSize }}</strong>
    </div>
    <EditorContent
      v-if="editor"
      :editor="editor"
      class="mail-body-editor__content"
      :style="{ minHeight }"
      @paste="handlePaste"
    />
    <div v-if="dragging" class="mail-body-editor__drop-mask">释放后插入图片</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { ElMessage } from 'element-plus'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import {
  deleteMailInlineImage,
  getMailInlineImageContent,
  uploadMailInlineImage
} from '@/api/mailInlineImages'

const MAX_IMAGE_BYTES = 2 * 1024 * 1024
const MAX_TOTAL_BYTES = 8 * 1024 * 1024
const MAX_IMAGE_COUNT = 5
const MAX_EDGE = 1920

const props = defineProps({
  modelValue: { type: String, default: '' },
  htmlValue: { type: String, default: '' },
  images: { type: Array, default: () => [] },
  imageOnly: Boolean,
  readonly: Boolean,
  minHeight: { type: String, default: '220px' }
})
const emit = defineEmits([
  'update:modelValue', 'update:htmlValue', 'update:images', 'uploading-change'
])

const uploading = ref(false)
const dragging = ref(false)
const syncing = ref(false)
const draftImageIds = new Set()
const objectUrls = new Map()
const fileQueue = []

const MailImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      mailImageId: {
        default: null,
        parseHTML: element => element.getAttribute('data-mail-image-id'),
        renderHTML: attributes => attributes.mailImageId
          ? { 'data-mail-image-id': attributes.mailImageId }
          : {}
      }
    }
  }
}).configure({ inline: false, allowBase64: false })

const textToHtml = (value) => (value || '').split('\n')
  .map(line => `<p>${escapeHtml(line) || '<br>'}</p>`).join('') || '<p><br></p>'
const escapeHtml = (value) => String(value)
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')

const editor = useEditor({
  content: props.htmlValue || (props.imageOnly ? '<p><br></p>' : textToHtml(props.modelValue)),
  editable: !props.readonly,
  extensions: [StarterKit.configure({ heading: false, link: false }), MailImage],
  editorProps: {
    attributes: { class: 'mail-body-editor__prose' },
    handleTextInput: () => props.imageOnly,
    handleKeyDown: (_view, event) => {
      if (!props.imageOnly) return false
      return !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Backspace', 'Delete'].includes(event.key)
    }
  },
  onUpdate: ({ editor: current }) => {
    if (syncing.value) return
    emit('update:htmlValue', current.getHTML())
    if (!props.imageOnly) emit('update:modelValue', current.getText({ blockSeparator: '\n' }).trim())
    const usedIds = new Set(extractImageIds(current.getJSON()))
    const remaining = props.images.filter(item => usedIds.has(String(item.id)))
    if (remaining.length !== props.images.length) {
      const removed = props.images.filter(item => !usedIds.has(String(item.id)))
      emit('update:images', remaining)
      removed.forEach(item => removeDraftOnServer(item.id))
    }
  }
})

const totalSize = computed(() => props.images.reduce((sum, item) => sum + Number(item.file_size || 0), 0))
const formattedTotalSize = computed(() => `${(totalSize.value / 1024 / 1024).toFixed(2)}MB`)

function extractImageIds(node) {
  if (!node) return []
  const own = node.type === 'image' && node.attrs?.mailImageId ? [String(node.attrs.mailImageId)] : []
  return [...own, ...(node.content || []).flatMap(extractImageIds)]
}

function setBusy(value) {
  uploading.value = value
  emit('uploading-change', value)
}

async function compressImage(file) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    throw new Error('仅支持 JPEG、PNG、WebP 图片')
  }
  if (file.size > 12 * 1024 * 1024) throw new Error('原始图片不能超过 12MB')
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(bitmap.width * scale))
  canvas.height = Math.max(1, Math.round(bitmap.height * scale))
  const context = canvas.getContext('2d')
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  const preferredType = file.type === 'image/png' ? 'image/png' : 'image/jpeg'
  let blob = await canvasBlob(canvas, preferredType, 0.85)
  for (const quality of [0.78, 0.7, 0.62]) {
    if (blob.size <= MAX_IMAGE_BYTES) break
    blob = await canvasBlob(canvas, 'image/jpeg', quality)
  }
  if (blob.size > MAX_IMAGE_BYTES) throw new Error('图片压缩后仍超过 2MB，请降低分辨率后重试')
  const extension = blob.type === 'image/png' ? '.png' : '.jpg'
  const baseName = (file.name || '正文图片').replace(/\.[^.]+$/, '')
  return new File([blob], `${baseName}${extension}`, { type: blob.type })
}

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => canvas.toBlob(
    blob => blob ? resolve(blob) : reject(new Error('图片压缩失败')),
    type,
    quality
  ))
}

async function addFile(file) {
  if (props.readonly) return
  fileQueue.push(file)
  if (uploading.value) return
  setBusy(true)
  try {
    while (fileQueue.length) {
      if (props.images.length >= MAX_IMAGE_COUNT) {
        fileQueue.splice(0)
        ElMessage.warning('每封邮件最多插入 5 张图片')
        break
      }
      const nextFile = fileQueue.shift()
      try {
        const compressed = await compressImage(nextFile)
        if (totalSize.value + compressed.size > MAX_TOTAL_BYTES) throw new Error('正文图片合计不能超过 8MB')
        const saved = await uploadMailInlineImage(compressed)
        const previewUrl = URL.createObjectURL(compressed)
        objectUrls.set(String(saved.id), previewUrl)
        draftImageIds.add(String(saved.id))
        emit('update:images', [...props.images, saved])
        editor.value?.chain().focus().setImage({
          src: previewUrl,
          alt: saved.original_name,
          mailImageId: String(saved.id)
        }).run()
        await nextTick()
      } catch (error) {
        ElMessage.error(getLocalizedErrorMessage(error, '图片上传失败'))
      }
    }
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '图片上传失败'))
  } finally {
    setBusy(false)
  }
}

function handlePaste(event) {
  if (props.readonly) return
  const files = [...(event.clipboardData?.items || [])]
    .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
    .map(item => item.getAsFile()).filter(Boolean)
  if (!files.length) return
  event.preventDefault()
  files.slice(0, MAX_IMAGE_COUNT - props.images.length).forEach(addFile)
}

function handleDrop(event) {
  dragging.value = false
  if (props.readonly) return
  const files = [...(event.dataTransfer?.files || [])].filter(file => file.type.startsWith('image/'))
  files.slice(0, MAX_IMAGE_COUNT - props.images.length).forEach(addFile)
}

async function removeDraftOnServer(id) {
  const key = String(id)
  if (!draftImageIds.has(key)) return
  draftImageIds.delete(key)
  try { await deleteMailInlineImage(id) } catch { /* 服务端兜底清理孤儿草稿 */ }
  const url = objectUrls.get(key)
  if (url) URL.revokeObjectURL(url)
  objectUrls.delete(key)
}

async function hydrateImages() {
  if (!editor.value) return
  for (const image of props.images) {
    const key = String(image.id)
    if (objectUrls.has(key)) continue
    try {
      const blob = await getMailInlineImageContent(image.id)
      objectUrls.set(key, URL.createObjectURL(blob))
    } catch { /* 编辑器仍保留 alt 文本，发送端会再次校验 */ }
  }
  const json = editor.value.getJSON()
  const replaceSources = node => {
    if (node.type === 'image' && node.attrs?.mailImageId) {
      node.attrs.src = objectUrls.get(String(node.attrs.mailImageId)) || node.attrs.src || ''
    }
    ;(node.content || []).forEach(replaceSources)
  }
  replaceSources(json)
  syncing.value = true
  editor.value.commands.setContent(json, false)
  syncing.value = false
}

watch(() => props.readonly, value => editor.value?.setEditable(!value))
watch(() => props.images, hydrateImages, { deep: true, immediate: true })
watch(() => [props.htmlValue, props.modelValue], ([htmlValue, modelValue]) => {
  if (!editor.value || syncing.value) return
  const incoming = htmlValue || (props.imageOnly ? '<p><br></p>' : textToHtml(modelValue))
  const currentIds = extractImageIds(editor.value.getJSON()).join(',')
  const incomingIds = [...incoming.matchAll(/data-mail-image-id=["']([^"']+)["']/g)].map(item => item[1]).join(',')
  if (incomingIds !== currentIds || (!incomingIds && incoming !== editor.value.getHTML())) {
    syncing.value = true
    editor.value.commands.setContent(incoming, false)
    syncing.value = false
    hydrateImages()
  }
})

async function cleanupDraftImages() {
  await Promise.all([...draftImageIds].map(removeDraftOnServer))
}

function markImagesSaved() {
  draftImageIds.clear()
}

defineExpose({ cleanupDraftImages, markImagesSaved })

onBeforeUnmount(() => {
  cleanupDraftImages()
  objectUrls.forEach(url => URL.revokeObjectURL(url))
  objectUrls.clear()
})
</script>

<style scoped>
.mail-body-editor{position:relative;border:1px solid var(--el-border-color);border-radius:6px;background:#fff;overflow:hidden}.mail-body-editor.is-dragging{border-color:var(--el-color-primary)}.mail-body-editor__toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px;border-bottom:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);font-size:12px;color:var(--el-text-color-secondary)}.mail-body-editor__toolbar strong{margin-left:auto;color:var(--el-text-color-regular)}.mail-body-editor__content{overflow-y:auto}.mail-body-editor__drop-mask{position:absolute;inset:0;z-index:3;display:flex;align-items:center;justify-content:center;background:rgba(64,158,255,.12);color:var(--el-color-primary);font-weight:600;pointer-events:none}:deep(.mail-body-editor__prose){min-height:inherit;padding:12px;outline:none;line-height:1.65;white-space:pre-wrap;word-break:break-word}:deep(.mail-body-editor__prose p){margin:0 0 6px}:deep(.mail-body-editor__prose img){display:block;max-width:100%;max-height:420px;margin:10px 0;border-radius:4px;object-fit:contain}:deep(.ProseMirror-selectednode){outline:2px solid var(--el-color-primary)}.is-readonly{background:#f1f5f9}
</style>
