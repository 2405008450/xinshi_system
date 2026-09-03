<template>
  <div class="mail-signature-editor">
    <div class="mail-signature-toolbar">
      <el-button-group>
        <el-button
          size="small"
          :type="editor?.isActive('bold') ? 'primary' : 'default'"
          @click="editor?.chain().focus().toggleBold().run()"
        >加粗</el-button>
        <el-button
          size="small"
          :type="editor?.isActive('italic') ? 'primary' : 'default'"
          @click="editor?.chain().focus().toggleItalic().run()"
        >斜体</el-button>
        <el-button
          size="small"
          :type="editor?.isActive('underline') ? 'primary' : 'default'"
          @click="editor?.chain().focus().toggleUnderline().run()"
        >下划线</el-button>
      </el-button-group>
      <span class="color-label">文字颜色</span>
      <el-color-picker v-model="selectedColor" size="small" :predefine="predefinedColors" @change="applyColor" />
      <el-button size="small" @click="clearFormatting">清除格式</el-button>
    </div>
    <EditorContent v-if="editor" :editor="editor" class="mail-signature-content" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Mark } from '@tiptap/core'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'

const props = defineProps({
  modelValue: { type: String, default: '' },
  textValue: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'update:textValue'])

const selectedColor = ref('#1f2937')
const predefinedColors = ['#1f2937', '#475569', '#64748b', '#2563eb', '#0f766e', '#b45309', '#b91c1c']
let syncing = false

const TextColor = Mark.create({
  name: 'textColor',
  addAttributes() {
    return {
      color: {
        default: null,
        parseHTML: element => element.style.color || null,
        renderHTML: attributes => attributes.color ? { style: `color:${attributes.color};` } : {}
      }
    }
  },
  parseHTML() {
    return [{ tag: 'span[style*="color"]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', HTMLAttributes, 0]
  }
})

const editor = useEditor({
  content: props.modelValue || '<p><br></p>',
  extensions: [StarterKit.configure({ heading: false, link: false }), TextColor],
  editorProps: { attributes: { class: 'mail-signature-prose' } },
  onSelectionUpdate: ({ editor: current }) => {
    selectedColor.value = current.getAttributes('textColor').color || '#1f2937'
  },
  onUpdate: ({ editor: current }) => {
    if (syncing) return
    emit('update:modelValue', current.isEmpty ? '' : current.getHTML())
    emit('update:textValue', current.getText({ blockSeparator: '\n' }).trim())
  }
})

const applyColor = color => {
  if (!color) return
  editor.value?.chain().focus().setMark('textColor', { color }).run()
}

const clearFormatting = () => {
  editor.value?.chain().focus().unsetAllMarks().run()
  selectedColor.value = '#1f2937'
}

watch(() => props.modelValue, value => {
  if (!editor.value) return
  const incoming = value || '<p><br></p>'
  if (incoming === editor.value.getHTML()) return
  syncing = true
  editor.value.commands.setContent(incoming, false)
  syncing = false
})

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.mail-signature-editor{border:1px solid var(--el-border-color);border-radius:6px;background:#fff;overflow:hidden}.mail-signature-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 10px;border-bottom:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}.color-label{color:var(--el-text-color-secondary);font-size:12px}.mail-signature-content{min-height:260px;max-height:420px;overflow-y:auto}:deep(.mail-signature-prose){min-height:260px;padding:14px;outline:none;line-height:1.65;white-space:pre-wrap;word-break:break-word}:deep(.mail-signature-prose p){margin:0 0 7px}:deep(.mail-signature-prose ul),:deep(.mail-signature-prose ol){padding-left:24px}
</style>
