<template>
  <div class="chat-inline-editor" @click.stop @contextmenu.stop @keydown.stop="onKeydown">
    <RichTextComposer
      v-if="richText"
      ref="richRef"
      v-model="draftJson"
      chat-screenshots
      :disabled="saving"
      placeholder="编辑消息内容…"
      @update:plain-text="draftPlain = $event"
      @uploading-change="uploading = $event"
    />
    <el-input
      v-else
      ref="inputRef"
      v-model="draftText"
      type="textarea"
      :autosize="{ minRows: 2, maxRows: 8 }"
      maxlength="10000"
      :disabled="saving"
      placeholder="编辑消息内容…"
    />
    <div v-if="preservedNotice" class="chat-inline-editor__hint">{{ preservedNotice }}</div>
    <div v-if="localError || error" class="chat-inline-editor__error" role="alert">{{ localError || error }}</div>
    <div class="chat-inline-editor__footer">
      <span class="chat-inline-editor__shortcut">Ctrl+Enter 保存 · Esc 取消</span>
      <el-button size="small" :disabled="saving" @click="emit('cancel')">取消</el-button>
      <el-button type="primary" size="small" :loading="saving" :disabled="uploading || saving" @click="submit">保存</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import { screenshotIds, screenshotText, screenshotValue } from '@/utils/screenshotReferences'

const DISCUSSION_FILE_PATTERN = /\[附件\]\(discussion-file:\/\/[0-9a-f-]{36}\)/gi

const props = defineProps({
  message: { type: Object, required: true },
  saving: Boolean,
  error: { type: String, default: '' },
  richText: Boolean,
  preserveDiscussionFiles: Boolean,
})

const emit = defineEmits(['save', 'cancel'])

const inputRef = ref()
const richRef = ref()
const uploading = ref(false)
const localError = ref('')

const rawContent = String(props.message?.content || '')
const preservedDiscussionFiles = props.preserveDiscussionFiles
  ? (rawContent.match(DISCUSSION_FILE_PATTERN) || [])
  : []
const contentWithoutDiscussionFiles = props.preserveDiscussionFiles
  ? rawContent.replace(DISCUSSION_FILE_PATTERN, '').trim()
  : rawContent
const preservedScreenshots = props.richText ? [] : screenshotIds(contentWithoutDiscussionFiles)

const draftText = ref(props.richText ? '' : screenshotText(contentWithoutDiscussionFiles))
const draftJson = ref(
  props.richText && props.message?.contentJson
    ? JSON.parse(JSON.stringify(props.message.contentJson))
    : { type: 'doc', content: [{ type: 'paragraph' }] },
)
const draftPlain = ref(props.richText ? rawContent : '')

const hasAttachments = computed(() =>
  Boolean((props.message?.attachments || []).length || preservedScreenshots.length || preservedDiscussionFiles.length),
)

const preservedNotice = computed(() => {
  const parts = []
  if (props.message?.reply) parts.push('原引用')
  if ((props.message?.attachments || []).length || preservedDiscussionFiles.length) parts.push('原附件')
  if (preservedScreenshots.length) parts.push('原截图')
  return parts.length ? `保存时将保留${parts.join('、')}` : ''
})

function buildFinalText() {
  let combined = preservedScreenshots.length
    ? screenshotValue(draftText.value, preservedScreenshots)
    : draftText.value.trim()
  if (preservedDiscussionFiles.length) {
    combined = [combined.trim(), ...preservedDiscussionFiles].filter(Boolean).join('\n')
  }
  return combined.trim()
}

function submit() {
  if (props.saving || uploading.value) return
  localError.value = ''
  if (props.richText) {
    const plain = String(draftPlain.value || '').trim()
    if (!plain && !hasAttachments.value) {
      localError.value = '消息内容不能为空'
      return
    }
    if (plain.length > 10000) {
      localError.value = '消息内容不能超过 10000 字'
      return
    }
    const unchanged = plain === rawContent.trim()
      && JSON.stringify(draftJson.value || null) === JSON.stringify(props.message?.contentJson || null)
    if (unchanged) {
      emit('cancel')
      return
    }
    emit('save', { content: plain, contentJson: draftJson.value })
    return
  }
  const finalContent = buildFinalText()
  if (!finalContent && !hasAttachments.value) {
    localError.value = '消息内容不能为空'
    return
  }
  if (finalContent.length > 10000) {
    localError.value = '消息内容不能超过 10000 字'
    return
  }
  if (finalContent === rawContent.trim()) {
    emit('cancel')
    return
  }
  emit('save', { content: finalContent })
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    if (!props.saving) emit('cancel')
    return
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    submit()
  }
}

onMounted(async () => {
  await nextTick()
  if (props.richText) {
    richRef.value?.focus?.()
  } else {
    inputRef.value?.focus?.()
    const textarea = inputRef.value?.textarea
    if (textarea) {
      const end = textarea.value.length
      textarea.setSelectionRange(end, end)
    }
  }
})
</script>

<style scoped>
.chat-inline-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: min(360px, 72vw);
  max-width: 100%;
}
.chat-inline-editor__hint {
  font-size: 11px;
  color: #64748b;
}
.chat-inline-editor__error {
  font-size: 12px;
  color: var(--el-color-danger, #dc2626);
}
.chat-inline-editor__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.chat-inline-editor__shortcut {
  margin-right: auto;
  font-size: 11px;
  color: #94a3b8;
}
@media (max-width: 640px) {
  .chat-inline-editor {
    min-width: min(260px, 76vw);
  }
  .chat-inline-editor__shortcut {
    display: none;
  }
}
</style>
