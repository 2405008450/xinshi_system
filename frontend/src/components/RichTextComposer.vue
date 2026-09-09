<template>
  <div class="rich-editor">
    <div v-if="editor" class="rich-editor__toolbar">
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
          size="small"
          :predefine="predefinedColors"
          @change="applyTextColor"
        />
        <el-button
          size="small"
          :type="editor.isActive('highlight') ? 'warning' : ''"
          @click="editor.chain().focus().toggleMark('highlight', { color: '#fff59d' }).run()"
        >黄色高亮</el-button>
        <el-button size="small" @click="clearFormatting">清除格式</el-button>
      </template>
      <el-button size="small" @click="editor.chain().focus().undo().run()">撤销</el-button>
      <el-button size="small" @click="editor.chain().focus().redo().run()">重做</el-button>
    </div>
    <EditorContent :editor="editor" class="rich-editor__content" />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { TextColor, YellowHighlight } from '@/utils/richTextMarks'

const props = defineProps({
  modelValue: { type: Object, default: null },
  placeholder: { type: String, default: '请输入留言内容…' },
  formatColors: Boolean,
  minHeight: { type: String, default: '132px' }
})

const emit = defineEmits(['update:modelValue', 'update:plainText'])

const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const minHeight = computed(() => props.minHeight)
const selectedColor = ref('#1f2937')
const predefinedColors = ['#1f2937', '#475569', '#2563eb', '#0f766e', '#b45309', '#b91c1c', '#7e22ce']

const editor = useEditor({
  content: props.modelValue || emptyDocument(),
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      link: false
    }),
    TextColor,
    YellowHighlight
  ],
  editorProps: {
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
      editor.value.commands.setContent(value, false)
    }
  }
)

defineExpose({
  clear: () => editor.value?.commands.setContent(emptyDocument(), false),
  focus: () => editor.value?.commands.focus()
})
</script>

<style scoped>
.rich-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  overflow: hidden;
}

.rich-editor__toolbar {
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
