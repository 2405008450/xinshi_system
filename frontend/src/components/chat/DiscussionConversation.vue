<template>
  <section class="discussion-chat" aria-label="资源讨论会话">
    <div v-if="searchOpen" class="discussion-chat__search"><el-input v-model="keyword" clearable placeholder="搜索此讨论的消息" maxlength="200" @keyup.enter="refresh(true)" /><el-button @click="searchOpen = false; keyword = ''">关闭</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button v-if="!loading" link @click="refresh(true)">重试</el-button></el-alert>
    <div ref="list" class="discussion-chat__timeline" @scroll="onScroll">
      <el-button v-if="hasEarlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="discussion-chat__hint">正在加载消息…</div>
      <el-empty v-else-if="!messages.length && !error" :description="keyword ? '没有匹配的消息' : '暂无消息，开始讨论吧'" :image-size="50" />
      <template v-for="(message, index) in messages" :key="message.id">
        <div v-if="!index || chatDayKey(message.createdAt) !== chatDayKey(messages[index - 1].createdAt)" class="discussion-chat__date">{{ chatDateLabel(message.createdAt, new Date(), true) }}</div>
        <article class="discussion-chat__message" :class="{ 'is-own': message.senderUserId === currentUserId }">
          <p v-if="message.recalledAt" class="discussion-chat__recalled">{{ message.senderName }}撤回了一条消息</p>
          <template v-else>
            <div class="discussion-chat__meta"><strong>{{ message.senderName }}</strong><time :title="formatBusinessDateTime(message.createdAt)">{{ chatClock(message.createdAt) }}</time></div>
            <div class="discussion-chat__bubble"><blockquote v-if="message.reply">{{ message.reply.senderName }}：{{ message.reply.content }}</blockquote><p>{{ message.content }}</p></div>
            <div class="discussion-chat__message-actions"><el-button link size="small" @click="replyTo = message; input?.focus()">引用</el-button><el-button v-if="message.canRecall" link size="small" @click="recall(message)">撤回</el-button></div>
          </template>
        </article>
      </template>
    </div>
    <el-button v-if="pendingNew" class="discussion-chat__new" @click="goBottom()">有新消息，点击查看</el-button>
    <div class="discussion-chat__composer">
      <div v-if="replyTo" class="discussion-chat__reply">回复 {{ replyTo.senderName }}：{{ replyTo.content }}<el-button link :disabled="sending" @click="replyTo = null">取消引用</el-button></div>
      <el-input ref="input" v-model="content" type="textarea" :rows="3" resize="none" maxlength="10000" placeholder="输入讨论消息" :disabled="!storageReady || sending || !!retryPayload" @keydown="keydown" />
      <div class="discussion-chat__footer"><span>Enter 发送 · Shift+Enter 换行</span><el-button v-if="retryPayload" :disabled="sending" @click="retryPayload = null; sendError = ''">继续编辑</el-button><el-button type="primary" :disabled="!storageReady || !canSend" :loading="sending" @click="send">{{ retryPayload ? '重试发送' : '发送' }}</el-button></div>
      <p v-if="sendError" class="discussion-chat__error" role="alert">{{ sendError }}</p>
    </div>
  </section>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { chatClock, chatDateLabel, chatDayKey } from '@/utils/chatLayout'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { subscribe } from '@/utils/realtimeSocket'
const props = defineProps({ projectId: { type: String, required: true }, active: Boolean })
const currentUserId = localStorage.getItem('user_id') || ''
const messages = ref([]), list = ref(), input = ref(), content = ref(''), replyTo = ref(null)
const loading = ref(false), loadingEarlier = ref(false), hasEarlier = ref(false), storageReady = ref(false)
const error = ref(''), sendError = ref(''), sending = ref(false), retryPayload = ref(null), pendingNew = ref(false)
const searchOpen = ref(false), keyword = ref('')
const canSend = computed(() => !sending.value && (!!retryPayload.value || !!content.value.trim()))
const base = `discussions/${props.projectId}`
let disposed = false, reading = false, requestVersion = 0, controller, pollTimer, searchTimer, readVersion = '0'
const atBottom = () => !list.value || list.value.scrollHeight - list.value.scrollTop - list.value.clientHeight < 50
const merge = rows => {
  const map = new Map(messages.value.map(row => [row.id, row]))
  for (const row of rows) map.set(row.id, row)
  messages.value = [...map.values()].sort((a, b) => BigInt(a.id) < BigInt(b.id) ? -1 : BigInt(a.id) > BigInt(b.id) ? 1 : 0)
  if (replyTo.value && map.get(replyTo.value.id)?.recalledAt) replyTo.value = null
}
async function markRead() {
  const last = messages.value.at(-1)?.id
  if (reading || !props.active || !storageReady.value || keyword.value || !last || BigInt(last) <= BigInt(readVersion)) return
  reading = true
  try { await chatRequest(`${base}/preferences`, { method: 'put', data: { readMessageId: last } }); readVersion = last } catch { /* 下轮重试，不能提前清除未读。 */ } finally { reading = false }
}
async function goBottom() { await nextTick(); if (list.value) list.value.scrollTop = list.value.scrollHeight; pendingNew.value = false; await markRead() }
function onScroll() { if (atBottom()) { pendingNew.value = false; markRead() } }
async function refresh(reset = false) {
  if (!props.active || disposed || ((loading.value || loadingEarlier.value) && !reset)) return
  controller?.abort(); controller = new AbortController(); const version = ++requestVersion
  const follow = reset || atBottom(), previousLast = messages.value.at(-1)?.id
  if (reset) { loading.value = true; messages.value = []; replyTo.value = null; pendingNew.value = false }
  try {
    const data = await chatRequest(`${base}/messages`, { params: { keyword: keyword.value.trim() }, signal: controller.signal })
    if (disposed || version !== requestVersion) return
    storageReady.value = true; error.value = ''; if (reset || !messages.value.length) hasEarlier.value = data.hasMore
    merge(data.items)
    if (follow) await goBottom()
    else if (previousLast !== messages.value.at(-1)?.id) pendingNew.value = true
  } catch (e) {
    if (disposed || version !== requestVersion || e.code === 'ERR_CANCELED') return
    error.value = e.message || '加载讨论消息失败'; if ([503, 403, 404].includes(e.status || e.response?.status)) storageReady.value = false
  } finally { if (version === requestVersion) loading.value = false }
}
async function loadEarlier() {
  if (loadingEarlier.value || !hasEarlier.value || !messages.value.length) return
  loadingEarlier.value = true; const version = requestVersion, height = list.value?.scrollHeight || 0
  try {
    const data = await chatRequest(`${base}/messages`, { params: { before: messages.value[0].id, keyword: keyword.value.trim() } })
    if (disposed || version !== requestVersion) return
    merge(data.items); hasEarlier.value = data.hasMore; await nextTick(); if (list.value) list.value.scrollTop += list.value.scrollHeight - height
  } catch (e) { if (!disposed && version === requestVersion) error.value = e.message } finally { loadingEarlier.value = false }
}
function newClientId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
async function send() {
  if (!storageReady.value || !canSend.value) return
  const payload = retryPayload.value || { content: content.value.trim(), clientMessageId: newClientId(), replyToId: replyTo.value?.id || null }
  sending.value = true; sendError.value = ''
  try {
    const row = await chatRequest(`${base}/messages`, { method: 'post', data: payload })
    if (disposed) return
    retryPayload.value = null; content.value = ''; replyTo.value = null
    if (keyword.value) { keyword.value = ''; await refresh(true) } else { merge([row]); await goBottom() }
    await nextTick(); input.value?.focus()
  } catch (e) { if (!disposed) { retryPayload.value = payload; sendError.value = e.message || '发送失败，请重试' } } finally { sending.value = false }
}
function keydown(event) { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); send() } }
async function recall(message) {
  try { const row = await chatRequest(`${base}/messages/${message.id}/recall`, { method: 'put' }); if (!disposed) merge([row]) }
  catch (e) { if (!disposed) error.value = e.message }
}
watch(keyword, value => { clearTimeout(searchTimer); controller?.abort(); ++requestVersion; searchTimer = setTimeout(() => refresh(true), value ? 400 : 0) })
watch(() => props.active, active => { clearInterval(pollTimer); if (active) { refresh(!messages.value.length); pollTimer = setInterval(() => refresh(), 5000) } else { controller?.abort(); ++requestVersion; loading.value = false } }, { immediate: true })
const unsubscribe = subscribe('chat_sessions_changed', () => { if (props.active && !sending.value) refresh() })
onBeforeUnmount(() => { disposed = true; controller?.abort(); clearInterval(pollTimer); clearTimeout(searchTimer); unsubscribe() })
defineExpose({ openSearch: () => { searchOpen.value = true } })
</script>
<style scoped>
.discussion-chat{display:flex;flex-direction:column;height:100%;min-height:0;background:#f6f8fb;color:#334155;font-size:13px}.discussion-chat__search{display:flex;gap:8px;padding:10px;background:white}.discussion-chat__timeline{flex:1;min-height:0;overflow-y:auto;padding:16px;overflow-anchor:none}.discussion-chat__date{text-align:center;color:#94a3b8;font-size:11px;margin:12px 0}.discussion-chat__message{margin:12px 0}.discussion-chat__meta{display:flex;align-items:center;gap:8px;margin-bottom:5px;color:#64748b;font-size:11px}.discussion-chat__meta strong{font-weight:500}.discussion-chat__bubble{width:fit-content;max-width:85%;padding:10px 13px;border:1px solid #e2e8f0;border-radius:12px;background:white;overflow-wrap:anywhere}.discussion-chat__bubble p{white-space:pre-wrap;line-height:1.7;margin:0;user-select:text}.discussion-chat__bubble blockquote{margin:0 0 7px;padding:5px 8px;border-left:2px solid #94a3b8;background:#f1f5f9;color:#64748b;white-space:pre-wrap;font-size:11px}.discussion-chat__message.is-own .discussion-chat__meta,.discussion-chat__message.is-own .discussion-chat__message-actions{justify-content:flex-end}.discussion-chat__message.is-own .discussion-chat__bubble{margin-left:auto;background:#e9f0fb;border-color:#d4e0f3}.discussion-chat__message-actions{display:flex;gap:8px;opacity:0}.discussion-chat__message:hover .discussion-chat__message-actions,.discussion-chat__message:focus-within .discussion-chat__message-actions{opacity:1}.discussion-chat__message-actions .el-button{font-size:10px;color:#94a3b8}.discussion-chat__recalled,.discussion-chat__hint{text-align:center;color:#94a3b8;font-size:12px}.discussion-chat__composer{flex:none;margin:10px 14px 14px;padding:10px;border:1px solid #dfe5ee;border-radius:12px;background:white}.discussion-chat__composer :deep(.el-textarea__inner){box-shadow:none;background:#fff}.discussion-chat__footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:8px}.discussion-chat__footer>span{margin-right:auto;font-size:11px;color:#94a3b8}.discussion-chat__reply{display:flex;align-items:center;justify-content:space-between;max-height:65px;overflow:auto;padding:5px 8px;background:#f1f5f9;font-size:12px;overflow-wrap:anywhere}.discussion-chat__error{color:#b91c1c;font-size:12px;margin:5px 0}.discussion-chat__new{align-self:center}@media(max-width:600px){.discussion-chat__footer>span{display:none}.discussion-chat__bubble{max-width:94%}}
</style>
