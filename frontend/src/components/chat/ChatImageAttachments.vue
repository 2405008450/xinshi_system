<template>
  <div class="chat-images">
    <el-upload v-if="showTools" :show-file-list="false" :auto-upload="false" :on-change="selectImage"
      accept="image/jpeg,image/png,image/gif,image/webp" multiple :disabled="disabled || items.length >= 9">
      <el-button text size="small" :icon="Picture" aria-label="发送图片" title="发送图片" :disabled="disabled || items.length >= 9" />
    </el-upload>
    <el-upload v-if="showTools && (allowFiles || toolsOnly)" :show-file-list="false" :auto-upload="false" :on-change="selectImage" multiple :disabled="disabled || items.length >= 9">
      <el-button text size="small" :icon="Paperclip" aria-label="发送文件" title="发送文件" :disabled="disabled || items.length >= 9" />
    </el-upload>
    <span v-if="!toolsOnly && items.length" class="chat-images__hint">每条最多9个附件，图片20MB（10MB以内保留原图），文件20MB</span>
    <div v-for="item in items" :key="item.key" class="chat-images__item">
      <img v-if="item.file.type.startsWith('image/')" :src="item.url" :alt="item.file.name" /><span>{{ item.file.name }}</span>
      <span v-if="item.status === 'uploading'">上传中…</span>
      <span v-else-if="item.status === 'failed'" role="alert" class="chat-images__error">{{ typeof item.error === 'string' ? item.error : '图片上传失败，请重试' }}</span>
      <span v-else>待发送</span>
      <el-button v-if="item.status === 'failed'" link :disabled="disabled" @click="$emit('retry', item)">重试</el-button>
      <el-button link :disabled="disabled" @click="$emit('remove', item.key)">移除</el-button>
    </div>
  </div>
</template>

<script setup>
import { Picture, Paperclip } from '@element-plus/icons-vue'
defineProps({ items: { type: Array, required: true }, disabled: Boolean, allowFiles:Boolean, toolsOnly:Boolean, showTools:{type:Boolean,default:true} })
const emit = defineEmits(['add', 'retry', 'remove'])
const selectImage = (file, files) => {
  emit('add', [file.raw])
  // 文件由草稿队列维护，避免 el-upload 长期保留已移除的文件。
  files.splice(0)
}
</script>

<style scoped>
.chat-images{display:flex;align-items:center;gap:8px;flex-wrap:wrap;max-height:180px;overflow-y:auto;padding-top:8px}
.chat-images__hint{font-size:12px;color:var(--el-text-color-secondary)}
.chat-images__item{display:flex;align-items:center;gap:6px;border:1px solid var(--el-border-color);border-radius:6px;padding:4px;font-size:12px}
.chat-images__item img{width:64px;height:48px;object-fit:contain}
.chat-images__error{max-width:160px;overflow-wrap:anywhere;color:var(--el-color-danger)}
</style>
