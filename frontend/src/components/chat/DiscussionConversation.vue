<template>
  <section class="discussion-chat" aria-label="资源讨论会话">
    <TechnicalRequirementsPanel ref="technicalPanel" :room-id="projectId" :active="active" @loaded="technicalRoom=$event" />
    <div v-if="searchOpen" class="discussion-chat__search"><el-input v-model="keyword" clearable placeholder="搜索此讨论的消息" maxlength="200" @keyup.enter="refresh(true)" /><el-checkbox v-model="favoritesOnly">只看收藏</el-checkbox><el-button @click="searchOpen = false; keyword = ''; favoritesOnly=false">关闭</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button v-if="!loading" link @click="refresh(true)">重试</el-button></el-alert>
    <div ref="list" class="discussion-chat__timeline" @scroll="onScroll">
      <div class="chat-timeline-content" style="display: flow-root">
      <el-button v-if="hasEarlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="discussion-chat__hint">正在加载消息…</div>
      <el-empty v-else-if="!messages.length && !error" :description="keyword ? '没有匹配的消息' : '暂无消息，开始讨论吧'" :image-size="50" />
      <template v-for="(message, index) in messages" :key="message.id">
        <div v-if="showMessageDates && (!index || chatDayKey(message.createdAt) !== chatDayKey(messages[index - 1].createdAt))" class="discussion-chat__date"><span>{{ formatMessageDay(message.createdAt) }}</span></div>
        <article :data-message-id="message.id" :ref="el=>messageInteractions.observe(el,message)" class="discussion-chat__message" :class="{ 'is-own': message.senderUserId === currentUserId, 'is-grouped': !chatGroupStart(message, messages[index - 1]), 'is-mentioned': mentionsMe(message), 'is-sending': message.optimisticStatus === 'sending', 'is-failed': message.optimisticStatus === 'failed' }">
          <span v-if="!message.recalledAt && message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])" class="discussion-chat__avatar" aria-hidden="true">{{ chatAvatarText(message.senderName) }}</span>
          <div v-if="!message.recalledAt && ((message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])) || (showMessageTime && timestampIndexes.has(index)))" class="discussion-chat__meta"><strong v-if="message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])">{{ message.senderName }}</strong><time v-if="showMessageTime && timestampIndexes.has(index)" :title="chatMessageTime(message.createdAt)">{{ chatMessageTime(message.createdAt) }}</time></div>
          <div v-if="undisplayedMentions(message,currentUserId).length" class="discussion-chat__mention-recipients" aria-label="消息提及人员"><span v-for="item in undisplayedMentions(message,currentUserId)" :key="item.id" :class="{'discussion-mention-highlight':item.highlight}">{{ item.label }}</span></div>
          <ChatRecalledMessage v-if="message.recalledAt" :message="message" :can-reedit="recallDrafts.canReedit(message)" @reedit="reeditMessage" />
          <template v-else>
            <div class="discussion-chat__message-main"><div class="discussion-chat__bubble" tabindex="0" data-message-menu-anchor @contextmenu="!message.optimisticStatus && messageMenu?.open($event,message)" @keydown="!message.optimisticStatus && messageMenu?.openKeyboard($event,message)"><blockquote v-if="message.reply"><span class="chat-quote-clamp">{{ message.reply.senderName }}：{{ screenshotPreview(message.reply.content) }}</span></blockquote><ChatMessageInlineEditor v-if="editingMessageId === message.id" :message="message" :saving="editingSaving" :error="editingError" preserve-discussion-files @save="payload => saveEdit(message, payload)" @cancel="cancelEdit" /><template v-else><p><template v-for="(part,partIndex) in mentionParts(message,currentUserId)" :key="partIndex"><span :class="{'discussion-mention-highlight':part.highlight}"><template v-for="(seg,segIndex) in splitUrgentText(part.text.replace(/\[附件\]\(discussion-file:\/\/[0-9a-f-]{36}\)/gi,''))" :key="segIndex"><span v-if="seg.urgent" class="chat-urgent-badge">急</span><ScreenshotText v-else :text="seg.text" :chat-message-id="message.id" chat-kind="discussion" /></template></span></template></p><span v-if="message.editedAt" class="chat-edited-tag" :title="`已编辑于 ${chatMessageTime(message.editedAt)}`">已编辑</span></template><DiscussionFileReferences :text="message.content" :room-id="projectId" /></div>
            <button v-if="!message.optimisticStatus" type="button" class="chat-message-more" aria-label="消息操作" @click="messageMenu?.open($event,message)">⋯</button>
            <span v-else-if="message.optimisticStatus === 'sending'" class="chat-optimistic-sending" role="status">发送中…</span>
            <span v-else-if="message.optimisticStatus === 'failed'" class="chat-optimistic-failed" role="alert" :title="message.optimisticError || '发送失败'">
              <span>发送失败</span>
              <button type="button" class="chat-optimistic-action" @click="retryOptimisticMessage(message)">重试</button>
              <button type="button" class="chat-optimistic-action is-muted" @click="removeOptimisticMessage(message)">移除</button>
            </span>
            </div>
            <ChatMessageActions :message="message" :current-user-id="currentUserId" :stats="messageInteractions.stats[message.id]" :views-available="messageInteractions.viewsAvailable.value" @acknowledge="acknowledge" @reply="quoteMessage" @references="(id,event)=>references.open(id,event)" />
          </template>
        </article>
      </template>
      </div>
    </div>
    <el-button v-if="pendingNew" class="discussion-chat__new" @click="goBottom()">有新消息，点击查看</el-button>
    <div class="discussion-chat__composer">
      <div v-if="replyTo" class="discussion-chat__reply"><span class="chat-compose-reply__text">回复 {{ replyTo.senderName }}：{{ screenshotPreview(replyTo.content) }}</span><button type="button" class="chat-compose-reply__close" aria-label="取消引用" title="取消引用" :disabled="sending || !!retryPayload" @click="cancelQuote"><el-icon><Close /></el-icon></button></div>
      <DiscussionMentionInput :room-id="projectId" ref="input" v-model="content" :users="mentionUsers" :selected-users="mentionSelection.selectedUsers||[]" :disabled="!storageReady || sending || !!retryPayload" @mention-open="ensureMentionUsers" @selection="mentionSelection=$event" @uploading-change="screenshotUploading=$event" @send="send" />
      <small v-if="draft.error.value" role="alert">{{draft.error.value}}</small>
      <div class="discussion-chat__footer"><span class="discussion-chat__shortcut">Enter 发送 · Shift+Enter 换行</span><el-button v-if="retryPayload" size="small" :disabled="sending" @click="retryPayload = null; sendError = ''">继续编辑</el-button><el-button type="primary" size="small" :disabled="!storageReady || !canSend" :loading="sending" @click="send">{{ retryPayload ? '重试发送' : '发送' }}</el-button></div>
      <p v-if="sendError" class="discussion-chat__error" role="alert">{{ sendError }}</p>
    </div>
    <ChatMessageContextMenu ref="messageMenu" :messages="messages" :current-user-id="currentUserId" :handlers="menuHandlers" project-type="discussion" :project-id="projectId" :active="active" />
    <ChatMessageReferences ref="references" :project-id="projectId" project-type="discussion" @locate="locate" />
    <TechnicalTaskDialog v-if="taskDraft" dialog-only :initial-content="taskDraft.content" @close="taskDraft = null" />
  </section>
</template>
<script setup>
import { useChatAutoScroll } from '@/composables/useChatAutoScroll'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import {useChatDraft} from '@/composables/useChatDraft'
import ChatRecalledMessage from './ChatRecalledMessage.vue'
import ChatMessageInlineEditor from './ChatMessageInlineEditor.vue'
import { useRecalledMessageDrafts } from '@/composables/useRecalledMessageDrafts'
import { combineRecallDraft } from '@/utils/recallDrafts'
import {quoteSpeakerMention,clearAutomaticQuoteMention} from '@/utils/quoteSpeakerMention'
import DiscussionMentionInput from './DiscussionMentionInput.vue'
import DiscussionFileReferences from './DiscussionFileReferences.vue'
import {mentionParts,undisplayedMentions} from '@/utils/chatMentions'
import { screenshotPreview } from '@/utils/screenshotReferences'
import ChatMessageActions from './ChatMessageActions.vue'
import ChatMessageContextMenu from './ChatMessageContextMenu.vue'
import TechnicalRequirementsPanel from './TechnicalRequirementsPanel.vue'
import { copyTextToClipboard } from '@/utils/clipboard'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import ChatMessageReferences from './ChatMessageReferences.vue'
import { useChatMessageInteractions } from '@/composables/useChatMessageInteractions'
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { canViewTechnicalDevelopment } from '@/utils/technicalDevelopmentAccess'
import { chatRequest } from '@/api/projectChat'
import { discussionMessagePayload } from '@/utils/discussionMessagePayload'
import { chatAvatarText, chatDayKey, chatGroupStart, chatTimestampIndexes } from '@/utils/chatLayout'
const splitUrgentText = text => {
  const value = String(text || '')
  if (!value.includes('**急**')) return [{ text: value }]
  return value.split(/(\*\*急\*\*)/).filter(Boolean).map(seg => seg === '**急**' ? { urgent: true } : { text: seg })
}
import { useChatTimeDisplay } from '@/composables/useChatTimeDisplay'
const { formatMessageTime: chatMessageTime, formatMessageDay, showMessageTime, showMessageDates } = useChatTimeDisplay()
import { formatBusinessDateTime } from '@/utils/dateTime'
import { subscribe } from '@/utils/realtimeSocket'
import { createCoalescedRefresh } from '@/utils/coalescedRefresh'
import { CHAT_MEMBERS_REFRESH_MS, CHAT_WINDOW_REFRESH_MS, createChatWindowFreshness } from '@/utils/chatWindowFreshness'
import { createOptimisticMessage, isOptimisticMessage, mergeWithOptimistic } from '@/utils/chatOptimistic'
import { loadOutboxMessages, markOutboxInFlight, removeOutboxMessage, sendWithAutoRetry, unmarkOutboxInFlight, upsertOutboxMessage } from '@/utils/chatOutbox'
const props = defineProps({ projectId: { type: String, required: true }, roomTitle: { type: String, default: '' }, active: Boolean, targetMessageId: { type: String, default: '' } })
const TechnicalTaskDialog = defineAsyncComponent(() => import('@/views/technology/TechnicalDevelopment.vue'))
const taskDraft = ref(null)
const canCreateDevelopmentTask = computed(() => props.roomTitle.replace(/\s/g, '') === '技术/开发沟通' && canViewTechnicalDevelopment())
function createDevelopmentTask(message, excerpt) {
  if (!canCreateDevelopmentTask.value || message.recalledAt) return
  const content = excerpt || message.content || ''
  if (content.length > 100000) { ElMessage.warning('聊天记录超过具体任务的10万字上限，请选取部分内容后添加'); return }
  taskDraft.value = { content }
}
const currentUserId = localStorage.getItem('user_id') || ''
const currentUserName = localStorage.getItem('user_name') || localStorage.getItem('username') || '我'
const outboxScope = () => ({ userId: currentUserId, projectType: 'discussion', projectId: String(props.projectId || '') })
const { refresh: refreshSessions } = useAnnotationFollowed()
const recallDrafts = useRecalledMessageDrafts(computed(() => ['discussion', props.projectId]))
const messages = ref([]), list = ref(), input = ref(), content = ref(''), replyTo = ref(null)
const timestampIndexes = computed(() => chatTimestampIndexes(messages.value))
const references=ref(), messageMenu=ref()
const technicalPanel=ref(),technicalRoom=ref(null)
const messageInteractions=useChatMessageInteractions({projectId:computed(()=>props.projectId),projectType:computed(()=>'discussion'),messages,active:computed(()=>props.active)})
const mentionsMe = message => !message?.recalledAt && (message?.mentions || []).some(item => String(item.mentionedUserId ?? item.mentioned_user_id) === String(currentUserId))
const loading = ref(false), loadingEarlier = ref(false), hasEarlier = ref(false), storageReady = ref(false)
const error = ref(''), sendError = ref(''), sending = ref(false), retryPayload = ref(null), pendingNew = ref(false)
const searchOpen = ref(false), keyword = ref(''), favoritesOnly=ref(false)
const screenshotUploading=ref(false)
const mentionUsers=ref([]),mentionSelection=ref({mentionedUserIds:[],mentionAll:false})
const automaticQuoteMention=ref(null)
function selectedMentionPeople(){return mentionSelection.value.selectedUsers || (mentionSelection.value.mentionedUserIds||[]).map(id=>mentionUsers.value.find(person=>person.id===id)||{id})}
function applyQuoteMention(result){content.value=result.content;automaticQuoteMention.value=result.automatic;mentionSelection.value={selectedUsers:result.selectedUsers,mentionedUserIds:result.selectedUsers.filter(person=>!person.all&&person.id!=='__all__').map(person=>person.id),mentionAll:result.selectedUsers.some(person=>person.all||person.id==='__all__')};if(result.warning)ElMessage.warning(result.warning)}
async function quoteMessage(message){if(sending.value||retryPayload.value)return;await ensureMentionUsers();if(!canRefresh()||sending.value||retryPayload.value)return;const result=quoteSpeakerMention({content:content.value,selectedUsers:selectedMentionPeople(),automatic:automaticQuoteMention.value,message,currentUserId,users:mentionUsers.value});replyTo.value=message;applyQuoteMention(result);await nextTick();input.value?.focus()}
function cancelQuote(){if(sending.value||retryPayload.value)return;applyQuoteMention(clearAutomaticQuoteMention(content.value,selectedMentionPeople(),automaticQuoteMention.value));replyTo.value=null}
watch(replyTo,value=>{if(!value&&automaticQuoteMention.value)applyQuoteMention(clearAutomaticQuoteMention(content.value,selectedMentionPeople(),automaticQuoteMention.value))})
async function loadMentionUsers() {
  const markFresh = memberFreshness.begin()
  try {
    const group = await chatRequest(`${base}/group`)
    if (disposed) return
    mentionUsers.value = [...(group.eligibleUsers || []), ...(group.invitableUsers || []).map(person => ({ ...person, outside: true }))]
    markFresh()
  } catch { /* 暂时繁忙时保留上次获得的候选人。 */ }
}
const canSend = computed(() => !screenshotUploading.value && !sending.value && (!!retryPayload.value || !!content.value.trim()))
const base = `discussions/${props.projectId}`
let disposed = false, reading = false, requestVersion = 0, controller, pollTimer, searchTimer, readVersion = '0'
let pendingFilterReset = false
const canRefresh = () => !disposed && props.active && document.visibilityState === 'visible'
const messageFreshness = createChatWindowFreshness(CHAT_WINDOW_REFRESH_MS)
const memberFreshness = createChatWindowFreshness(CHAT_MEMBERS_REFRESH_MS)
const messageRefresh = createCoalescedRefresh(refresh, { visible: canRefresh, minIntervalMs: 1500 })
let membersRequest
function ensureMentionUsers() {
  if (!canRefresh() || !memberFreshness.isStale()) return Promise.resolve()
  membersRequest ??= loadMentionUsers().finally(() => { membersRequest = undefined })
  return membersRequest
}
const atBottom = () => !list.value || list.value.scrollHeight - list.value.scrollTop - list.value.clientHeight < 50
const compareDiscussionMessages = (a, b) => BigInt(a.id) < BigInt(b.id) ? -1 : BigInt(a.id) > BigInt(b.id) ? 1 : 0
const lastRealMessageId = () => [...messages.value].reverse().find(row => !isOptimisticMessage(row))?.id
const firstRealMessageId = () => messages.value.find(row => !isOptimisticMessage(row))?.id
const merge = (rows, options = {}) => {
  const scope = outboxScope()
  for (const row of rows) {
    const cid = row?.clientMessageId || row?.client_message_id
    if (cid && !isOptimisticMessage(row)) removeOutboxMessage(scope, cid)
  }
  messages.value = mergeWithOptimistic(messages.value, rows, {
    replaceTempId: options.replaceTempId || '',
    compareReal: compareDiscussionMessages,
  })
  const map = new Map(messages.value.map(row => [row.id, row]))
  if (replyTo.value && map.get(replyTo.value.id)?.recalledAt) replyTo.value = null
  if (editingMessageId.value && map.get(editingMessageId.value)?.recalledAt) { editingMessageId.value = ''; editingError.value = '' }
}
watch(storageReady, ready => {
  if (!ready || keyword.value || favoritesOnly.value) return
  const pending = loadOutboxMessages(outboxScope()).filter(item => !messages.value.some(row => !isOptimisticMessage(row) && (row.clientMessageId || row.client_message_id) === item.clientMessageId))
  if (pending.length) merge(pending)
})
async function markRead() {
  const last = lastRealMessageId()
  if (reading || !canRefresh() || !document.hasFocus() || !storageReady.value || keyword.value || !last || BigInt(last) <= BigInt(readVersion)) return
  reading = true
  try { await chatRequest(`${base}/preferences`, { method: 'put', data: { readMessageId: last } }); readVersion = last } catch { /* 下轮重试，不能提前清除未读。 */ } finally { reading = false }
}
const autoScroll = useChatAutoScroll(() => list.value, () => props.active)
async function goBottom() { await autoScroll.bottom(); pendingNew.value = false; await markRead() }
function onScroll() { if (atBottom()) { pendingNew.value = false; markRead() } }
async function refresh(reset = false) {
  if (!props.active || disposed || ((loading.value || loadingEarlier.value) && !reset)) return
  controller?.abort(); controller = new AbortController(); const version = ++requestVersion
  const signal = controller.signal
  if (reset) { pendingFilterReset = false; messageFreshness.invalidate() }
  const markFresh = messageFreshness.begin()
  const follow = reset || atBottom(), previousLast = [...messages.value].reverse().find(row => !row?.optimisticStatus)?.id
  if (reset) { loading.value = true; messages.value = []; replyTo.value = null; pendingNew.value = false }
  try {
    const data = await chatRequest(`${base}/messages`, { params: { keyword: keyword.value.trim(), favorites_only:favoritesOnly.value || undefined }, signal })
    if (disposed || version !== requestVersion) return
    const missed = []
    const firstRecent = data.items[0]?.id
    if (!reset && !keyword.value.trim() && !favoritesOnly.value && data.hasMore && previousLast && firstRecent) {
      let after = previousLast
      // 断线时最新一页可能与本地消息完全错开，按游标补齐中间的消息。
      while (BigInt(after) < BigInt(firstRecent)) {
        const page = await chatRequest(`${base}/messages`, { params: { after, limit: 100 }, signal })
        if (disposed || version !== requestVersion) return
        missed.push(...page.items.filter(row => BigInt(row.id) < BigInt(firstRecent)))
        const last = page.items.at(-1)?.id
        if (!page.hasMore || !last || BigInt(last) <= BigInt(after)) break
        after = last
      }
    }
    storageReady.value = true; error.value = ''; if (reset || !messages.value.length) hasEarlier.value = data.hasMore
    merge([...missed, ...data.items])
    markFresh()
    if (follow) await goBottom()
    else if (previousLast !== [...messages.value].reverse().find(row => !row?.optimisticStatus)?.id) pendingNew.value = true
  } catch (e) {
    if (disposed || version !== requestVersion || e.code === 'ERR_CANCELED') return
    error.value = e.message || '加载讨论消息失败'; if ([503, 403, 404].includes(e.status || e.response?.status)) storageReady.value = false
  } finally { if (version === requestVersion) loading.value = false }
}
async function loadEarlier() {
  const firstId = firstRealMessageId()
  if (loadingEarlier.value || !hasEarlier.value || !firstId) return
  autoScroll.pause()
  loadingEarlier.value = true; const version = requestVersion, height = list.value?.scrollHeight || 0
  try {
    const data = await chatRequest(`${base}/messages`, { params: { before: firstId, keyword: keyword.value.trim(), favorites_only:favoritesOnly.value || undefined } })
    if (disposed || version !== requestVersion) return
    merge(data.items); hasEarlier.value = data.hasMore; await nextTick(); if (list.value) list.value.scrollTop += list.value.scrollHeight - height
  } catch (e) { if (!disposed && version === requestVersion) error.value = e.message } finally { loadingEarlier.value = false }
}
function newClientId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
function updateOptimisticMessage(tempId, patch) {
  const index = messages.value.findIndex(item => item.id === tempId)
  if (index < 0) return
  const next = [...messages.value]
  next[index] = { ...next[index], ...patch }
  messages.value = next
}
async function deliverOptimisticMessage(tempMessage) {
  const payload = tempMessage.optimisticPayload
  if (!payload) return
  const scope = outboxScope()
  const roomName = props.roomTitle || ''
  const sendingCopy = { ...tempMessage, optimisticStatus: 'sending', optimisticError: '' }
  updateOptimisticMessage(tempMessage.id, { optimisticStatus: 'sending', optimisticError: '' })
  upsertOutboxMessage(scope, sendingCopy)
  markOutboxInFlight(tempMessage.clientMessageId)
  try {
    const row = await sendWithAutoRetry(() => chatRequest(`${base}/messages`, { method: 'post', data: payload }))
    removeOutboxMessage(scope, tempMessage.id)
    if (disposed) {
      if (payload.replyToId) void refreshSessions()
      return
    }
    if (payload.replyToId) void refreshSessions()
    if (keyword.value) {
      keyword.value = ''
      await refresh(true)
    } else {
      const follow = atBottom()
      merge([row], { replaceTempId: tempMessage.id })
      if (follow) await goBottom()
    }
  } catch (e) {
    const errText = e.message || '发送失败，请重试'
    upsertOutboxMessage(scope, { ...tempMessage, optimisticStatus: 'failed', optimisticError: errText })
    if (!disposed) {
      updateOptimisticMessage(tempMessage.id, { optimisticStatus: 'failed', optimisticError: errText })
    }
    ElMessage.error(roomName ? `「${roomName}」有消息发送失败，请重试` : `消息发送失败，请重试：${errText}`)
  } finally {
    unmarkOutboxInFlight(tempMessage.clientMessageId)
  }
}
function retryOptimisticMessage(message) {
  if (!message || message.optimisticStatus !== 'failed') return
  void deliverOptimisticMessage(message)
}
function removeOptimisticMessage(message) {
  if (!message || !isOptimisticMessage(message)) return
  removeOutboxMessage(outboxScope(), message.id)
  messages.value = messages.value.filter(item => item.id !== message.id)
}
async function send() {
  if (!storageReady.value || !canSend.value) return
  const payload = discussionMessagePayload(retryPayload.value || { content: content.value.trim(), clientMessageId: newClientId(), ...mentionSelection.value, replyToId: replyTo.value?.id || null })
  sendError.value = ''
  const tempMessage = createOptimisticMessage({
    clientMessageId: payload.clientMessageId,
    senderUserId: currentUserId,
    senderName: currentUserName,
    content: payload.content,
    reply: replyTo.value,
    payload,
  })
  retryPayload.value = null
  content.value = ''
  replyTo.value = null
  mentionSelection.value = { mentionedUserIds: [], mentionAll: false }
  merge([tempMessage])
  await goBottom()
  await nextTick()
  input.value?.focus()
  void deliverOptimisticMessage(tempMessage)
}
function keydown(event) { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); send() } }
async function recall(message) {
  try { await ElMessageBox.confirm('撤回后其他用户将无法查看该消息，确定撤回？','确认撤回',{type:'warning',customClass:'chat-confirm-message-box'}); await recallDrafts.remember(message); const row = await chatRequest(`${base}/messages/${message.id}/recall`, { method: 'put' }); if (!disposed) merge([row]) }
  catch (e) { if (!disposed && e !== 'cancel' && e !== 'close') error.value = e.message }
}
const editingMessageId = ref(''), editingSaving = ref(false), editingError = ref('')
function startEdit(message) {
  if (!message || message.recalledAt || !message.canEdit) return
  editingMessageId.value = message.id
  editingError.value = ''
}
function cancelEdit() {
  if (editingSaving.value) return
  editingMessageId.value = ''
  editingError.value = ''
}
async function saveEdit(message, payload) {
  if (editingSaving.value || !message) return
  editingSaving.value = true
  editingError.value = ''
  try {
    const row = await chatRequest(`${base}/messages/${message.id}`, { method: 'patch', data: payload })
    if (disposed) return
    merge([row])
    editingMessageId.value = ''
  } catch (e) {
    if (!disposed) editingError.value = e.detail || e.message || '编辑失败，请重试'
  } finally {
    editingSaving.value = false
  }
}
async function reeditMessage(message) {
  if (sending.value || retryPayload.value) return ElMessage.warning('请先处理当前正在发送或发送失败的消息')
  const recovered = await recallDrafts.restore(message)
  if (!recovered || sending.value || retryPayload.value) return
  try {
    const result = combineRecallDraft({ content: content.value, mentionIds: [...(mentionSelection.value.mentionedUserIds || []), ...(mentionSelection.value.mentionAll ? ['__all__'] : [])], replyTo: replyTo.value }, recovered)
    content.value = result.content; replyTo.value = result.replyTo
    const selectedUsers = result.mentionIds.map(id => id === '__all__' ? { id, name: '所有人', all: true } : mentionUsers.value.find(person => String(person.id) === id) || recovered.mentions.find(person => person.id === id)).filter(Boolean)
    mentionSelection.value = { selectedUsers, mentionedUserIds: result.mentionIds.filter(id => id !== '__all__'), mentionAll: result.mentionIds.includes('__all__') }
    sendError.value = ''; draft.persistNow(); recallDrafts.forget(message)
    await nextTick(); input.value?.focus()
  } catch (e) { ElMessage.warning(e.message) }
}
async function action(message, name, enabled) {
  try { const row=await chatRequest(`${base}/message-actions/${message.id}/${name}`,{method:enabled?'put':'delete'});if(!disposed)merge([row]) }
  catch(e){ElMessage.error(e.message||'操作失败')}
}
const acknowledge = message=>action(message,'acknowledgement',!message.isAcknowledged)
const menuHandlers=computed(()=>({
  copy:async(message,excerpt)=>{if(!await copyTextToClipboard(excerpt||message.content))ElMessage.error('复制失败，请使用 Ctrl+C')},
  reply:quoteMessage,
  favorite:message=>action(message,'favorite',!message.isFavorited),acknowledge,edit:startEdit,recall,
  ...(technicalRoom.value?{technical:message=>technicalPanel.value.append(message)}:{}),
  ...(canCreateDevelopmentTask.value ? { 'development-task': createDevelopmentTask } : {}),
}))
watch(favoritesOnly, () => { pendingFilterReset = true; void refresh(true) })
watch(keyword, value => {
  pendingFilterReset = true
  clearTimeout(searchTimer); controller?.abort(); ++requestVersion
  searchTimer = setTimeout(() => refresh(true), value ? 400 : 0)
})
watch(() => props.active, active => {
  clearInterval(pollTimer)
  if (active) {
    if (!storageReady.value || pendingFilterReset) {
      clearTimeout(searchTimer)
      void refresh(true)
    }
    else if (messageFreshness.isStale()) void messageRefresh.schedule({ immediate: true })
    else if (atBottom()) void markRead()
    pollTimer = setInterval(() => messageRefresh.schedule(), 15000 + Math.floor(Math.random() * 5000))
  } else { controller?.abort(); ++requestVersion; loading.value = false }
}, { immediate: true })
const cleanup = [
  subscribe('chat_sessions_changed', event => {
    if (event.projectType && (event.projectType !== 'discussion' || String(event.projectId) !== String(props.projectId))) return
    messageFreshness.invalidate()
    void messageRefresh.schedule()
    if (!event.projectType || event.membersChanged) memberFreshness.invalidate()
  }),
  ...['connected', 'chat_realtime_recovered'].map(event => subscribe(event, () => {
    messageFreshness.invalidate(); memberFreshness.invalidate()
    return messageRefresh.schedule()
  })),
  subscribe('foreground', () => {
    if (messageFreshness.isStale()) void messageRefresh.schedule()
    else if (atBottom()) void markRead()
  }),
]
let locatedTarget = ''
watch(() => [props.active, props.targetMessageId, loading.value, storageReady.value], ([active, id, busy, ready]) => {
  if (active && id && !busy && ready && locatedTarget !== id) { locatedTarget = id; locate(id) }
}, { flush: 'post' })
const draft=useChatDraft(computed(()=>['discussion',props.projectId]),()=>({content:content.value,mentionSelection:mentionSelection.value,replyTo:replyTo.value,automaticQuoteMention:automaticQuoteMention.value,retryPayload:retryPayload.value}),data=>{content.value=data.content;mentionSelection.value=data.mentionSelection||{mentionedUserIds:[],mentionAll:false};replyTo.value=data.replyTo||null;automaticQuoteMention.value=data.automaticQuoteMention||null;retryPayload.value=data.retryPayload||null})
onBeforeUnmount(() => {
  disposed = true; controller?.abort(); clearInterval(pollTimer); clearTimeout(searchTimer)
  messageRefresh.stop(); cleanup.forEach(unsubscribe => unsubscribe())
})
async function locate(id) {
  autoScroll.pause()
  try {
    const target=String(id)
    if(!messages.value.some(row=>row.id===target)){
      const [older,newer]=await Promise.all([chatRequest(`${base}/messages`,{params:{before:(BigInt(target)+1n).toString(),limit:30}}),chatRequest(`${base}/messages`,{params:{after:target,limit:30}})])
      merge([...(older.items||[]),...(newer.items||[])])
    }
    await nextTick();const element=list.value?.querySelector(`[data-message-id="${target}"]`);element?.scrollIntoView({block:'center'});element?.animate([{background:'#fef3c7'},{background:'transparent'}],{duration:2200})
  }catch(e){error.value=e.detail||e.message||'定位消息失败'}
}
defineExpose({ openSearch: () => { searchOpen.value = true }, locate })
</script>
<style scoped>
.discussion-chat__message-main{display:flex;align-items:center;gap:6px}.discussion-chat__message.is-own .discussion-chat__message-main{flex-direction:row-reverse}.discussion-chat__message-main .discussion-chat__bubble{margin-left:0;max-width:min(680px,calc(100% - 34px))}.discussion-chat__message:hover .chat-message-more,.discussion-chat__message:focus-within .chat-message-more{opacity:1}.discussion-mention-highlight{background:#fef3c7;color:#92400e;border-radius:4px;padding:0 3px;font-weight:500}.discussion-chat__meta{flex-wrap:wrap}.discussion-chat__meta time{overflow-wrap:anywhere}
.discussion-chat{display:flex;flex-direction:column;height:100%;min-height:0;background:var(--chat-stage-bg,#f4f6f9);color:var(--chat-text,#1e293b);font-size:13.5px}.discussion-chat__search{display:flex;gap:8px;padding:8px 12px;background:#fff;border-bottom:1px solid var(--chat-border,#e2e8f0)}.discussion-chat__timeline{flex:1;min-height:0;overflow-y:auto;padding:16px 20px;overflow-anchor:none}.discussion-chat__date{display:flex;justify-content:center;margin:18px 0}.discussion-chat__date>span{padding:2px 10px;border-radius:10px;background:#e8edf4;color:#64748b;font-size:11px;line-height:1.5}.discussion-chat__message{position:relative;padding-left:42px;margin:14px 0}.discussion-chat__message.is-own{padding-left:0}.discussion-chat__message.is-grouped{margin-top:-6px}.discussion-chat__avatar{position:absolute;left:0;top:1px;display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#e3ebf5;color:#3b526b;font-size:12.5px;font-weight:600;border:1px solid #d5e0ee}.discussion-chat__meta{display:flex;align-items:center;gap:8px;margin-bottom:4px;color:#64748b;font-size:12px}.discussion-chat__meta strong{font-weight:600;color:#334155}.discussion-chat__meta time{font-size:11px;color:#94a3b8;font-variant-numeric:tabular-nums}.discussion-chat__bubble{width:fit-content;max-width:min(680px,84%);padding:10px 13px;border:1px solid var(--chat-bubble-border,#e5eaf0);border-radius:4px 12px 12px 12px;background:var(--chat-bubble-bg,#fff);box-shadow:var(--chat-bubble-shadow,0 1px 2px rgba(15,23,42,.04));overflow-wrap:anywhere}.discussion-chat__bubble p{white-space:pre-wrap;line-height:1.65;margin:0;user-select:text;color:#1e293b}.discussion-chat__message.is-own .discussion-chat__meta,.discussion-chat__message.is-own .discussion-chat__message-actions{justify-content:flex-end}.discussion-chat__message.is-own .discussion-chat__bubble{margin-left:auto;border-radius:12px 4px 12px 12px;background:var(--chat-bubble-own-bg,#e3ecf6);border-color:var(--chat-bubble-own-border,#ccd9e8)}.discussion-chat__message.is-mentioned .discussion-chat__bubble{background:var(--chat-bubble-mention-bg,#fef9ec);border-color:#f3d99b;border-left:3px solid var(--chat-bubble-mention-accent,#d97706)}.chat-urgent-badge{display:inline-flex;align-items:center;justify-content:center;margin-right:5px;padding:0 5px;height:18px;border-radius:4px;background:#fee2e2;color:#dc2626;font-size:11px;font-weight:600;line-height:18px;vertical-align:1px}.discussion-chat__message-actions{display:flex;gap:8px;opacity:0}.discussion-chat__message:hover .discussion-chat__message-actions,.discussion-chat__message:focus-within .discussion-chat__message-actions{opacity:1}.discussion-chat__message-actions .el-button{font-size:10px;color:#94a3b8}.discussion-chat__recalled,.discussion-chat__hint{text-align:center;color:#94a3b8;font-size:12px}.discussion-chat__composer{flex:none;margin:10px 14px 14px;padding:8px 12px 10px;border:1px solid #dce4ee;border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.03);transition:border-color .14s ease,box-shadow .14s ease}.discussion-chat__composer:focus-within{border-color:var(--color-primary,#334155);box-shadow:0 0 0 3px rgba(51,65,85,.08)}.discussion-chat__composer :deep(.el-textarea__inner){box-shadow:none;background:#fff;padding:4px 2px;line-height:1.6;color:#1e293b}.discussion-chat__footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:6px}.discussion-chat__shortcut{margin-right:auto;font-size:11px;color:#94a3b8}.discussion-chat__reply{display:flex;align-items:center;justify-content:space-between;max-height:65px;overflow:auto;padding:6px 8px;background:#f1f5f9;font-size:12px;overflow-wrap:anywhere}.discussion-chat__error{color:#b91c1c;font-size:12px;margin:5px 0}.discussion-chat__new{align-self:center}@media(max-width:600px){.discussion-chat__shortcut{display:none}.discussion-chat__bubble{max-width:94%}.discussion-chat__timeline{padding:12px 10px}}
</style>

<style scoped src="./chatQuotes.css" />

<style scoped>
.discussion-chat__mention-recipients{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 5px;color:#334155;font-size:12px}.is-own .discussion-chat__mention-recipients{justify-content:flex-end}.discussion-chat__mention-recipients span{padding:1px 7px;border-radius:10px;background:#e8eef6;color:#334155;font-weight:500}.discussion-chat__mention-recipients span.discussion-mention-highlight{background:#fef3c7;color:#92400e}
.chat-edited-tag{display:inline-block;margin-top:4px;font-size:11px;color:#94a3b8}
.discussion-chat__message.is-sending .discussion-chat__bubble{opacity:.9}
.discussion-chat__message.is-failed .discussion-chat__bubble{border-color:#fca5a5}
.chat-optimistic-sending{font-size:11px;color:#94a3b8;white-space:nowrap;opacity:0;animation:chat-opt-fade .18s ease .4s forwards}
.chat-optimistic-failed{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#dc2626;white-space:nowrap}
.chat-optimistic-action{border:0;background:transparent;padding:0 2px;font:inherit;color:#2563eb;cursor:pointer}
.chat-optimistic-action:hover{text-decoration:underline}
.chat-optimistic-action.is-muted{color:#64748b}
@keyframes chat-opt-fade{to{opacity:1}}
</style>
