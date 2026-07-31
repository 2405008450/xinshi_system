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
      <el-button size="small" @click="editor.chain().focus().undo().run()">撤销</el-button>
      <el-button size="small" @click="editor.chain().focus().redo().run()">重做</el-button>
    </div>
    <EditorContent :editor="editor" class="rich-editor__content" />
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'

const props = defineProps({
  modelValue: { type: Object, default: null },
  placeholder: { type: String, default: '请输入留言内容…' }
})

const emit = defineEmits(['update:modelValue', 'update:plainText'])

const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })

const editor = useEditor({
  content: props.modelValue || emptyDocument(),
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      link: false
    })
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
  }
})

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
  min-height: 132px;
}

:deep(.rich-editor__prose) {
  min-height: 108px;
  padding: 12px;
  outline: none;
  line-height: 1.7;
  color: var(--el-text-color-primary);
}

:deep(.rich-editor__prose p:first-child:last-child:empty::before) {
  content: attr(data-placeholder);
  color: var(--el-text-color-placeholder);
  pointer-events: none;
}

:deep(.rich-editor__prose p) {
  margin: 0 0 8px;
}

:deep(.rich-editor__prose h1),
:deep(.rich-editor__prose h2),
:deep(.rich-editor__prose h3) {
  margin: 4px 0 10px;
}
</style>
