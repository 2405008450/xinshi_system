<template>
  <div class="chat-images">
    <el-upload :show-file-list="false" :auto-upload="false" :on-change="selectImage"
      accept="image/jpeg,image/png,image/gif,image/webp" multiple :disabled="disabled || items.length >= 9">
      <el-button size="small" :disabled="disabled || items.length >= 9">添加图片</el-button>
    </el-upload>
    <span class="chat-images__hint">可粘贴截图，每条最多 9 张，单张 10MB</span>
    <div v-for="item in items" :key="item.key" class="chat-images__item">
      <img :src="item.url" :alt="item.file.name" />
      <span v-if="item.status === 'uploading'">上传中…</span>
      <span v-else-if="item.status === 'failed'" role="alert" class="chat-images__error">{{ typeof item.error === 'string' ? item.error : '图片上传失败，请重试' }}</span>
      <span v-else>待发送</span>
      <el-button v-if="item.status === 'failed'" link :disabled="disabled" @click="$emit('retry', item)">重试</el-button>
      <el-button link :disabled="disabled" @click="$emit('remove', item.key)">移除</el-button>
    </div>
  </div>
</template>

<script setup>
defineProps({ items: { type: Array, required: true }, disabled: Boolean })
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
