<template>
  <div v-if="!message.recalledAt" class="chat-message-actions" :class="{'is-own': own}">
    <button type="button" @click="$emit('reply', message)">回复</button>
    <button v-if="!own && acknowledgeEnabled" type="button" :disabled="acknowledging" :class="{'is-active':message.isAcknowledged}" :title="message.isAcknowledged ? '再次点击可取消收到确认' : '让发送者知道你已确认收到'" @click="$emit('acknowledge',message)">{{ message.isAcknowledged ? '✓ 已收到' : '收到' }}</button>
    <span v-if="message.acknowledgements?.length" :title="message.acknowledgements.map(row => `${row.userName} · ${formatBusinessDateTime(row.acknowledgedAt)}`).join('\n')">{{ message.acknowledgements.map(row=>row.userName).join('、') }} 已收到</span>
    <button v-if="message.reply || stats?.replyCount" type="button" :title="stats?.replyUsers?.map(row=>row.name).join('、')" @click="$emit('references', stats?.replyCount ? message.id : message.reply?.id || message.id, $event)">{{ stats?.hasReplied ? '我已回复 · ' : '' }}{{ stats?.replyCount ? `${stats.replyCount} 条回复` : '查看引用' }}</button>
    <el-popover v-if="own" trigger="click" placement="top-end" :width="300" :z-index="readerZ" :disabled="viewsAvailable !== true || stats?.seenCount == null">
      <template #reference><button type="button" class="chat-message-actions__seen" :title="seenTooltip" aria-label="查看已读人数和阅读时间" @click="readerZ = chatOverlayZIndex($event.currentTarget)">{{ viewsAvailable === false ? '已读统计待启用' : stats?.seenCount != null ? `已读 ${stats.seenCount}/${stats.recipientCount}` : '已读统计加载中…' }}</button></template>
      <strong>阅读详情 · {{ stats?.seenCount || 0 }}/{{ stats?.recipientCount || 0 }} 人已读</strong>
      <p class="chat-reader-hint">不含发送者，显示首次阅读时间（UTC+8）</p>
      <div class="chat-reader-list"><div v-for="reader in stats?.seenUsers || []" :key="reader.id" class="chat-reader-row"><strong>{{ reader.name }}</strong><time>{{ formatBusinessDateTime(reader.seenAt) }}</time></div><p v-if="!stats?.seenUsers?.length" class="chat-reader-hint">暂无阅读记录</p></div>
    </el-popover>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props = defineProps({ message: {type:Object,required:true}, currentUserId: String, stats: Object, viewsAvailable: {default:null}, acknowledging: Boolean, acknowledgeEnabled: {type:Boolean,default:true} })
defineEmits(['reply','acknowledge','references'])
const own = computed(() => String(props.message.senderUserId) === String(props.currentUserId))
const readerZ = ref(2120)
const seenTooltip = computed(() => props.viewsAvailable === false ? '逐条阅读回执尚未启用；不会按关注状态推算已读' : props.stats?.seenUsers?.length ? props.stats.seenUsers.map(row=>`${row.name} · ${formatBusinessDateTime(row.seenAt)}`).join('\n') : '统计当前其他参与人实际查看此消息的情况，不包含自己')
</script>
<style scoped>
.chat-reader-hint{font-size:11px;color:#64748b;line-height:1.5}.chat-reader-list{max-height:min(280px,40vh);overflow-y:auto}.chat-reader-row{display:flex;flex-direction:column;gap:4px;padding:8px 0;border-bottom:1px solid #e2e8f0}.chat-reader-row time{font-size:11px;color:#64748b}
.chat-message-actions{display:flex;align-items:center;flex-wrap:wrap;gap:4px 10px;margin-top:4px;font-size:10px;color:#94a3b8;line-height:1.5}.chat-message-actions.is-own{justify-content:flex-end}.chat-message-actions button{border:0;background:none;padding:1px 0;font:inherit;color:#64748b;cursor:pointer}.chat-message-actions button:hover,.chat-message-actions button.is-active{color:#2563eb}.chat-message-actions button:disabled{opacity:.5;cursor:wait}.chat-message-actions__seen{font-variant-numeric:tabular-nums}
</style>
