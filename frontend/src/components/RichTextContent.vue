<template>
  <EditorContent v-if="editor" :editor="editor" class="rich-content" />
  <div v-else class="rich-content rich-content--plain">{{ fallback }}</div>
</template>

<script setup>
import { onBeforeUnmount, watch } from 'vue'
import { Editor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'

const props = defineProps({
  document: { type: Object, default: null },
  fallback: { type: String, default: '' }
})

const editor = props.document
  ? new Editor({
      content: props.document,
      editable: false,
      extensions: [StarterKit.configure({ link: false })]
    })
  : null

watch(
  () => props.document,
  (value) => {
    if (editor && value) editor.commands.setContent(value, false)
  },
  { deep: true }
)

onBeforeUnmount(() => editor?.destroy())
</script>

<style scoped>
.rich-content {
  line-height: 1.65;
  word-break: break-word;
  color: var(--el-text-color-regular);
}

.rich-content--plain {
  white-space: pre-wrap;
}

:deep(p) {
  margin: 0 0 8px;
}

:deep(p:last-child) {
  margin-bottom: 0;
}
</style>
