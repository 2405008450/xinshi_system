<template>
  <section class="chat-message-search" aria-label="全部会话聊天记录搜索">
    <p v-if="!keyword">输入关键词，搜索全部有权查看的会话聊天记录</p>
    <template v-else>
      <p role="status">{{ loading && !items.length ? '搜索中…' : `找到 ${total} 条聊天记录` }}</p>
      <p v-if="error" role="alert">{{ error }} <el-button link @click="load()">重试</el-button></p>
      <button v-for="item in items" :key="`${item.key}:${item.messageId}`" type="button" class="chat-message-search__item" @click="$emit('locate', item)">
        <strong>{{ item.title }}</strong><small>{{ item.subtitle }} · {{ item.senderName }} · {{ formatBusinessDateTime(item.createdAt) }}</small>
        <span>{{ screenshotPreview(item.preview) }}</span>
      </button>
      <el-button v-if="hasMore" text :loading="loading" @click="load(true)">加载更多</el-button>
    </template>
  </section>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { screenshotPreview } from '@/utils/screenshotReferences'
const props = defineProps({ keyword: { type: String, default: '' }, revision: Number })
defineEmits(['locate'])
const items = ref([]), total = ref(0), loading = ref(false), error = ref(''), hasMore = ref(false)
let controller, generation = 0
async function load(append = false) {
  controller?.abort()
  const version = ++generation
  controller = new AbortController()
  const current = controller, identity = localStorage.getItem('user_id')
  if (!append) { items.value = []; total.value = 0; hasMore.value = false }
  error.value = ''; loading.value = false
  if (!props.keyword) return
  loading.value = true
  try {
    const data = await chatRequest('messages/search', { params: { keyword: props.keyword, offset: append ? items.value.length : 0, limit: 30 }, signal: current.signal })
    if (version !== generation || identity !== localStorage.getItem('user_id')) return
    items.value = append ? [...items.value, ...data.items] : data.items
    total.value = data.total; hasMore.value = data.hasMore
  } catch (e) { if (version === generation && !current.signal.aborted) error.value = e.detail || e.message || '搜索失败' }
  finally { if (version === generation) loading.value = false }
}
watch(() => [props.keyword, props.revision], () => load(), { immediate: true })
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<style scoped>
.chat-message-search{padding:8px;color:#64748b;font-size:12px}.chat-message-search__item{display:flex;flex-direction:column;gap:5px;width:100%;padding:10px;border:0;border-bottom:1px solid #e2e8f0;background:transparent;text-align:left;cursor:pointer;color:#334155}.chat-message-search__item:hover{background:#e8eef7}.chat-message-search__item small{color:#64748b;font-size:11px}.chat-message-search__item span{white-space:pre-wrap;overflow-wrap:anywhere}.chat-message-search__item strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
