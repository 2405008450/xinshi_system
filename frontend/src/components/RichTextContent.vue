<template>
  <EditorContent v-if="editor" :editor="editor" class="rich-content" />
  <div v-else class="rich-content rich-content--plain">{{ fallback }}</div>
</template>

<script setup>
import { onBeforeUnmount, watch } from 'vue'
import { Editor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { TextColor, YellowHighlight } from '@/utils/richTextMarks'
import { linkifyDocument, noticeLinkOptions } from '@/utils/richTextLinks'
import { createAuthenticatedImage } from '@/utils/richTextImages'
import '@/styles/rich-text-images.css'

const props = defineProps({
  document: { type: Object, default: null },
  enableLinks: Boolean,
  imageApi: { type: Object, default: null },
  fallback: { type: String, default: '' }
})

const editor = props.document
  ? new Editor({
      content: props.enableLinks ? linkifyDocument(props.document) : props.document,
      editable: false,
      extensions: [StarterKit.configure({ link: props.enableLinks ? noticeLinkOptions : false }), TextColor, YellowHighlight,
        ...(props.imageApi ? [createAuthenticatedImage(props.imageApi.read)] : [])]
    })
  : null

watch(
  () => props.document,
  (value) => {
    if (editor && value) editor.commands.setContent(props.enableLinks ? linkifyDocument(value) : value, { emitUpdate: false })
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

:deep(a) {
  color: var(--el-color-primary);
  text-decoration: underline;
  cursor: pointer;
}
</style>
