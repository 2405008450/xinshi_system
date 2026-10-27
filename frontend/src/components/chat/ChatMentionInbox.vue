<template>
  <div class="chat-mention-inbox">
    <div class="chat-mention-inbox__heading" title="右键可调整排序；未读始终优先"><span>{{ keyword ? '搜索结果' : sortLabel }} · 未读优先</span><small>{{ total }} 条</small></div>
    <p v-if="error" class="chat-mention-inbox__error" role="alert">{{ error }} <el-button link @click="reload">重试</el-button></p>
    <div v-if="loading && !items.length" class="chat-mention-inbox__status" role="status">正在加载提及消息…</div>
    <el-empty v-else-if="!items.length && !error" :description="keyword ? '没有匹配的提及消息' : '暂无提及我的消息'" :image-size="48" />
    <button v-for="item in items" :key="item.messageId" type="button" class="chat-mention-inbox__message"
      :class="{ 'is-active': selectedMessageId === item.messageId }" :title="`${item.title} · ${item.senderName}：${screenshotPreview(item.preview)}`"
      @click="select(item)">
      <span class="chat-mention-inbox__avatar" aria-hidden="true">{{ chatAvatarText(item.senderName) }}</span>
      <span class="chat-mention-inbox__content">
        <span class="chat-mention-inbox__title"><strong>{{ item.title }}</strong><time :title="formatBusinessDateTime(item.createdAt)">{{ chatDateLabel(item.createdAt) }}</time></span>
        <span class="chat-mention-inbox__sender">{{ item.senderName }}<b v-if="item.unread">未读</b></span>
        <span class="chat-mention-inbox__preview"><mark>@我</mark> {{ screenshotPreview(item.preview) }}</span>
        <small class="chat-mention-inbox__source">{{ ({annotation:'标注项目群',translation:'笔译项目群',discussion:'讨论会话',direct:'私聊'})[item.projectType] || '会话' }}<template v-if="item.subtitle"> · {{ item.subtitle }}</template></small>
      </span>
    </button>
    <div v-if="hasMore" class="chat-mention-inbox__status"><el-button link type="primary" :loading="loading" @click="loadMore">加载更多</el-button></div>
  </div>
</template>

<script setup>
import { screenshotPreview } from '@/utils/screenshotReferences'
import { computed, ref, toRef, watch } from 'vue'
import { mentionSortOptions } from '@/utils/chatMentionSort'
import { useChatMentions } from '@/composables/useChatMentions'
import { chatAvatarText, chatDateLabel } from '@/utils/chatLayout'
import { formatBusinessDateTime } from '@/utils/dateTime'

const props = defineProps({ keyword: { type: String, default: '' }, active: { type: Boolean, default: true }, filters: { type: Object, default: () => ({}) } })
const emit = defineEmits(['locate', 'total'])
const selectedMessageId = ref('')
const sortLabel = computed(() => mentionSortOptions.find(option => option.value === (props.filters.sort || 'time_desc'))?.label)
const { items, total, loading, error, hasMore, reload, loadMore } = useChatMentions(toRef(props, 'keyword'), toRef(props, 'active'), toRef(props, 'filters'))
watch(total, value => emit('total', value), { immediate: true })
watch([() => props.keyword, () => props.filters], () => { selectedMessageId.value = '' })
function select(item) { selectedMessageId.value = item.messageId; emit('locate', item) }
</script>

<style scoped>
.chat-mention-inbox{padding:0 6px 8px;min-width:0}
.chat-mention-inbox__heading{display:flex;justify-content:space-between;padding:10px 6px;color:#94a3b8;font-size:12px}
.chat-mention-inbox__message{display:flex;gap:10px;width:100%;box-sizing:border-box;padding:12px 8px;margin-bottom:4px;border:0;border-radius:8px;background:transparent;color:#334155;text-align:left;cursor:pointer;font:inherit}
.chat-mention-inbox__message:hover,.chat-mention-inbox__message.is-active{background:#e9eff9}
.chat-mention-inbox__message:focus-visible{outline:2px solid #5479be;outline-offset:-2px}
.chat-mention-inbox__avatar{display:grid;place-items:center;flex:none;width:36px;height:36px;border-radius:10px;background:#e1e9f8;color:#5479be;font-size:14px}
.chat-mention-inbox__content{display:flex;flex:1;min-width:0;flex-direction:column;gap:5px}
.chat-mention-inbox__title{display:flex;align-items:center;gap:6px}
.chat-mention-inbox__title strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:600}
.chat-mention-inbox__title time{flex:none;font-size:10px;color:#94a3b8}
.chat-mention-inbox__sender{display:flex;align-items:center;gap:6px;font-size:11px;color:#64748b}
.chat-mention-inbox__sender b{color:#dc2626;font-size:10px;font-weight:500}
.chat-mention-inbox__preview{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere;font-size:12px;line-height:1.6}
.chat-mention-inbox__preview mark{border-radius:3px;background:#fef3c7;color:#92400e;padding:0 3px}
.chat-mention-inbox__source{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#94a3b8;font-size:10px}
.chat-mention-inbox__status{padding:16px;text-align:center;color:#94a3b8;font-size:12px}
.chat-mention-inbox__error{padding:8px;color:#b91c1c;font-size:12px}
</style>
