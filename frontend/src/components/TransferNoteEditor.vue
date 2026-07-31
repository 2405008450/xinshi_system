<template>
  <div class="transfer-note-editor">
    <RichTextComposer
      :model-value="modelValue.contentJson"
      placeholder="填写交接说明、当前进度和注意事项…"
      @update:model-value="patch({ contentJson: $event })"
      @update:plain-text="patch({ content: $event })"
    />
    <div class="attachment-row">
      <el-upload
        :show-file-list="false"
        :http-request="handleUpload"
        accept="image/jpeg,image/png,image/gif,image/webp"
        multiple
      >
        <el-button :loading="uploading" :disabled="attachments.length >= 9">添加图片</el-button>
      </el-upload>
      <span class="attachment-tip">支持 JPEG、PNG、GIF、WebP，单张不超过 10MB</span>
    </div>
    <div v-if="attachments.length" class="attachment-tags">
      <el-tag
        v-for="attachment in attachments"
        :key="attachment.id"
        closable
        @close="removeAttachment(attachment.id)"
      >
        {{ attachment.originalName }}
      </el-tag>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import RichTextComposer from '@/components/RichTextComposer.vue'
import { uploadProjectChatAttachment } from '@/api/projectChat'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])
const uploading = ref(false)
const attachments = computed(() => props.modelValue.attachments || [])

const patch = (value) => {
  emit('update:modelValue', { ...props.modelValue, ...value })
}

const handleUpload = async ({ file }) => {
  if (attachments.value.length >= 9) {
    ElMessage.warning('每次交接最多添加 9 张图片')
    return
  }
  uploading.value = true
  try {
    const attachment = await uploadProjectChatAttachment(file)
    patch({ attachments: [...attachments.value, attachment] })
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '图片上传失败')
  } finally {
    uploading.value = false
  }
}

const removeAttachment = (attachmentId) => {
  patch({ attachments: attachments.value.filter(item => item.id !== attachmentId) })
}
</script>

<style scoped>
.transfer-note-editor {
  display: grid;
  gap: 10px;
}

.attachment-row,
.attachment-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.attachment-tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
