<template>
  <div class="chat-mention-inbox">
    <div class="chat-mention-inbox__heading" title="右键可调整排序；未读始终优先">
      <span>{{ keyword ? '搜索结果' : sortLabel }} · 未读优先</span>
      <small>{{ total }} 条</small>
    </div>
    <div v-if="senders.length" class="chat-mention-inbox__senders" role="group" aria-label="按提及人筛选">
      <button type="button" class="chat-mention-sender-chip" :class="{ 'is-active': !activeSenderId }" :aria-pressed="!activeSenderId" @click="pickSender('')">全部</button>
      <button
        v-for="sender in visibleSenders"
        :key="sender.userId"
        type="button"
        class="chat-mention-sender-chip"
        :class="{ 'is-active': activeSenderId === sender.userId }"
        :aria-pressed="activeSenderId === sender.userId"
        :title="`${sender.name} · 共 ${sender.count} 条${sender.unreadCount ? `（未读 ${sender.unreadCount} 条）` : ''}`"
        @click="pickSender(sender.userId)"
      >
        <span class="chat-mention-sender-chip__name">{{ sender.name }}</span>
        <b v-if="sender.unreadCount" class="chat-mention-sender-chip__unread">{{ sender.unreadCount > 99 ? '99+' : sender.unreadCount }}</b>
        <small v-else class="chat-mention-sender-chip__count">{{ sender.count }}</small>
      </button>
      <button v-if="senders.length > defaultLimit" type="button" class="chat-mention-sender-chip chat-mention-sender-chip--more" @click="sendersExpanded = !sendersExpanded">
        {{ sendersExpanded ? '收起' : `展开 (${senders.length}人)` }}
      </button>
    </div>
    <p v-if="error" class="chat-mention-inbox__error" role="alert">{{ error }} <el-button link @click="reload">重试</el-button></p>
    <div v-if="loading && !items.length" class="chat-mention-inbox__status" role="status">正在加载提及消息…</div>
    <el-empty v-else-if="!items.length && !error" :description="keyword ? '没有匹配的提及消息' : activeSenderId ? '该用户暂无符合条件的提及消息' : filters.mentionKind === 'all' ? '暂无 @所有人 的消息' : '暂无提及我的消息'" :image-size="48" />
    <button v-for="item in items" :key="item.messageId" type="button" class="chat-mention-inbox__message"
      :class="{ 'is-active': selectedMessageId === item.messageId }" :title="`${item.title} · ${item.senderName}：${screenshotPreview(item.preview)}`"
      @click="select(item)">
      <span class="chat-mention-inbox__avatar" aria-hidden="true">{{ chatAvatarText(item.senderName) }}</span>
      <span class="chat-mention-inbox__content">
        <span class="chat-mention-inbox__title"><strong>{{ item.title }}</strong><time :title="formatBusinessDateTime(item.createdAt)">{{ chatDateLabel(item.createdAt) }}</time></span>
        <span class="chat-mention-inbox__sender">{{ item.senderName }}<b v-if="item.unread">未读</b></span>
        <span class="chat-mention-inbox__preview"><mark :class="{ 'is-broadcast': item.mentionAll }">{{ item.mentionAll ? '@所有人' : '@我' }}</mark> {{ screenshotPreview(item.preview) }}</span>
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
const emit = defineEmits(['locate', 'total', 'select-sender'])
const selectedMessageId = ref('')
const sendersExpanded = ref(false)
const defaultLimit = 5
const activeSenderId = computed(() => String(props.filters.senderId || ''))
const sortLabel = computed(() => mentionSortOptions.find(option => option.value === (props.filters.sort || 'time_desc'))?.label)
const { items, senders, total, loading, error, hasMore, reload, loadMore } = useChatMentions(toRef(props, 'keyword'), toRef(props, 'active'), toRef(props, 'filters'))
const visibleSenders = computed(() => {
  if (sendersExpanded.value || senders.value.length <= defaultLimit) return senders.value
  const base = senders.value.slice(0, defaultLimit)
  if (activeSenderId.value && !base.some(row => row.userId === activeSenderId.value)) {
    const selected = senders.value.find(row => row.userId === activeSenderId.value)
    if (selected) return [...base, selected]
  }
  return base
})
watch(total, value => emit('total', value), { immediate: true })
watch([() => props.keyword, () => props.filters], () => { selectedMessageId.value = '' })
function select(item) { selectedMessageId.value = item.messageId; emit('locate', item) }
function pickSender(id) { emit('select-sender', id && id === activeSenderId.value ? '' : id) }
</script>

<style scoped>
.chat-mention-inbox{padding:0 6px 8px;min-width:0}
.chat-mention-inbox__heading{display:flex;justify-content:space-between;padding:8px 6px 6px;color:#94a3b8;font-size:12px}
.chat-mention-inbox__senders{display:flex;flex-wrap:wrap;gap:5px;padding:0 6px 8px;margin-bottom:4px;border-bottom:1px solid #e9eef5}
.chat-mention-sender-chip{display:inline-flex;align-items:center;gap:4px;max-width:100%;height:24px;padding:0 8px;border:1px solid #dce4ee;border-radius:12px;background:#fff;color:#475569;font:inherit;font-size:11.5px;line-height:1;cursor:pointer;transition:background-color .12s ease,border-color .12s ease,color .12s ease}
.chat-mention-sender-chip:hover{background:#eef3f8;border-color:#cbd5e1;color:#1e293b}
.chat-mention-sender-chip.is-active{background:#334155;border-color:#334155;color:#fff;font-weight:500}
.chat-mention-sender-chip__name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:96px}
.chat-mention-sender-chip__count{font-size:10.5px;color:#94a3b8;font-variant-numeric:tabular-nums}
.chat-mention-sender-chip.is-active .chat-mention-sender-chip__count{color:rgba(255,255,255,.78)}
.chat-mention-sender-chip__unread{display:inline-flex;align-items:center;justify-content:center;min-width:15px;height:15px;padding:0 4px;border-radius:8px;background:#dc2626;color:#fff;font-size:10px;font-weight:600;line-height:1}
.chat-mention-sender-chip--more{border-style:dashed;background:transparent;color:#64748b}
.chat-mention-inbox__message{display:flex;gap:10px;width:100%;box-sizing:border-box;padding:10px 8px;margin-bottom:4px;border:1px solid transparent;border-radius:8px;background:transparent;color:#334155;text-align:left;cursor:pointer;font:inherit;transition:background-color .12s ease,border-color .12s ease}
.chat-mention-inbox__message:hover{background:#eff3f8;border-color:#dde5ef}
.chat-mention-inbox__message.is-active{background:#e7eef6;border-color:#c6d4e5}
.chat-mention-inbox__message:focus-visible{outline:2px solid #334155;outline-offset:-2px}
.chat-mention-inbox__avatar{display:grid;place-items:center;flex:none;width:36px;height:36px;border-radius:10px;background:#e4ebf4;color:#334155;border:1px solid #d7e1ee;font-size:14px;font-weight:600}
.chat-mention-inbox__content{display:flex;flex:1;min-width:0;flex-direction:column;gap:5px}
.chat-mention-inbox__title{display:flex;align-items:center;gap:6px}
.chat-mention-inbox__title strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:600;color:#1e293b}
.chat-mention-inbox__title time{flex:none;font-size:10.5px;color:#94a3b8;font-variant-numeric:tabular-nums}
.chat-mention-inbox__sender{display:flex;align-items:center;gap:6px;font-size:11px;color:#64748b}
.chat-mention-inbox__sender b{color:#dc2626;font-size:10px;font-weight:500}
.chat-mention-inbox__preview{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere;font-size:12px;line-height:1.6}
.chat-mention-inbox__preview mark{border-radius:3px;background:#fef3c7;color:#92400e;padding:0 3px}
.chat-mention-inbox__preview mark.is-broadcast{background:#ffedd5;color:#9a3412}
.chat-mention-inbox__source{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#94a3b8;font-size:10.5px}
.chat-mention-inbox__status{padding:16px;text-align:center;color:#94a3b8;font-size:12px}
.chat-mention-inbox__error{padding:8px;color:#b91c1c;font-size:12px}
</style>
