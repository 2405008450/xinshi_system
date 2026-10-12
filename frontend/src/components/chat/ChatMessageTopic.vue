<template>
  <span v-if="!message.recalledAt" class="chat-message-topic">
    <el-tag v-if="showTag && message.topicPath" size="small" effect="plain">{{ message.topicPath }}</el-tag>
    <el-popover v-if="message.canClassify" v-model:visible="visible" trigger="click" placement="bottom-end" :width="320" popper-class="chat-topic-popover" @show="draft = message.topicId || null">
      <template #reference><el-button link size="small" @click.stop>分类</el-button></template>
      <ChatTopicSelect v-model="draft" :disabled="saving" />
      <div class="chat-topic-edit-actions"><el-button size="small" :disabled="saving" @click="visible = false">取消</el-button><el-button size="small" type="primary" :loading="saving" @click="save">保存</el-button></div>
    </el-popover>
  </span>
</template>
<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { topicApi } from '@/api/chatTopics'
import { messageTopicPatch } from '@/utils/chatTopics'
import ChatTopicSelect from './ChatTopicSelect.vue'
const props = defineProps({ message: { type: Object, required: true }, showTag: { type: Boolean, default: true } })
const visible = ref(false), saving = ref(false), draft = ref(null)
async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const data = await topicApi.classify(props.message.id, { topic_id: draft.value, revision: props.message.topicRevision || 0 })
    const patch = messageTopicPatch(data)
    Object.assign(props.message, patch)
    window.dispatchEvent(new CustomEvent('chat-topic-message-changed', { detail: { id: props.message.id, ...patch } }))
    visible.value = false; ElMessage.success('消息分类已更新')
  } catch (error) {
    if (error.status === 409 || error.response?.status === 409) {
      try { Object.assign(props.message, messageTopicPatch(await topicApi.message(props.message.id))) } catch { /* 下次刷新仍可恢复服务器状态。 */ }
    }
    ElMessage.error(error.message)
  } finally { saving.value = false }
}
</script>
<style scoped>
.chat-message-topic{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap;max-width:100%}.chat-message-topic :deep(.el-tag){height:auto;white-space:normal;overflow-wrap:anywhere}.chat-topic-edit-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
</style>
<style>.chat-topic-popover{max-width:calc(100vw - 32px)!important;z-index:100000!important}.chat-topic-popover>.el-select{width:100%}</style>
