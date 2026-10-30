<template>
  <section class="discussion-chat" aria-label="资源讨论会话">
    <TechnicalRequirementsPanel ref="technicalPanel" :room-id="projectId" :active="active" @loaded="technicalRoom=$event" />
    <div v-if="searchOpen" class="discussion-chat__search"><el-input v-model="keyword" clearable placeholder="搜索此讨论的消息" maxlength="200" @keyup.enter="refresh(true)" /><el-checkbox v-model="favoritesOnly">只看收藏</el-checkbox><el-button @click="searchOpen = false; keyword = ''; favoritesOnly=false">关闭</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button v-if="!loading" link @click="refresh(true)">重试</el-button></el-alert>
    <div ref="list" class="discussion-chat__timeline" @scroll="onScroll">
      <el-button v-if="hasEarlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="discussion-chat__hint">正在加载消息…</div>
      <el-empty v-else-if="!messages.length && !error" :description="keyword ? '没有匹配的消息' : '暂无消息，开始讨论吧'" :image-size="50" />
      <template v-for="(message, index) in messages" :key="message.id">
        <div v-if="showMessageDates && (!index || chatDayKey(message.createdAt) !== chatDayKey(messages[index - 1].createdAt))" class="discussion-chat__date">{{ formatMessageDay(message.createdAt) }}</div>
        <article :data-message-id="message.id" :ref="el=>messageInteractions.observe(el,message)" class="discussion-chat__message" :class="{ 'is-own': message.senderUserId === currentUserId }">
          <div class="discussion-chat__meta"><strong v-if="!message.recalledAt">{{ message.senderName }}</strong><time v-if="showMessageTime && timestampIndexes.has(index)" :title="chatMessageTime(message.createdAt)">{{ chatMessageTime(message.createdAt) }}</time></div>
          <ChatRecalledMessage v-if="message.recalledAt" :message="message" :can-reedit="recallDrafts.canReedit(message)" @reedit="reeditMessage" />
          <template v-else>
            <div class="discussion-chat__message-main"><div class="discussion-chat__bubble" tabindex="0" data-message-menu-anchor @contextmenu="messageMenu?.open($event,message)" @keydown="messageMenu?.openKeyboard($event,message)"><blockquote v-if="message.reply" role="button" tabindex="0" @click="references.open(message.reply.id,$event)" @keydown.enter="references.open(message.reply.id,$event)">{{ message.reply.senderName }}：{{ screenshotPreview(message.reply.content) }}</blockquote><p @click="openMessageReferences(message,$event)"><span v-for="(part,partIndex) in mentionParts(message,currentUserId)" :key="partIndex" :class="{'discussion-mention-highlight':part.highlight}"><ScreenshotText :text="part.text" :chat-message-id="message.id" chat-kind="discussion" /></span></p></div>
            <button type="button" class="chat-message-more" aria-label="消息操作" @click="messageMenu?.open($event,message)">⋯</button></div>
            <ChatMessageActions :message="message" :current-user-id="currentUserId" :stats="messageInteractions.stats[message.id]" :views-available="messageInteractions.viewsAvailable.value" @acknowledge="acknowledge" @reply="quoteMessage" @references="(id,event)=>references.open(id,event)" />
          </template>
        </article>
      </template>
    </div>
    <el-button v-if="pendingNew" class="discussion-chat__new" @click="goBottom()">有新消息，点击查看</el-button>
    <div class="discussion-chat__composer">
      <div v-if="replyTo" class="discussion-chat__reply">回复 {{ replyTo.senderName }}：{{ screenshotPreview(replyTo.content) }}<el-button link :disabled="sending || !!retryPayload" @click="cancelQuote">取消引用</el-button></div>
      <DiscussionMentionInput ref="input" v-model="content" :users="mentionUsers" :selected-users="mentionSelection.selectedUsers||[]" :disabled="!storageReady || sending || !!retryPayload" @selection="mentionSelection=$event" @uploading-change="screenshotUploading=$event" @send="send" />
      <small v-if="draft.error.value" role="alert">{{draft.error.value}}</small>
      <div class="discussion-chat__footer"><el-button v-if="retryPayload" :disabled="sending" @click="retryPayload = null; sendError = ''">继续编辑</el-button><el-button type="primary" :disabled="!storageReady || !canSend" :loading="sending" @click="send">{{ retryPayload ? '重试发送' : '发送' }}</el-button></div>
      <p v-if="sendError" class="discussion-chat__error" role="alert">{{ sendError }}</p>
    </div>
    <ChatMessageContextMenu ref="messageMenu" :messages="messages" :current-user-id="currentUserId" :handlers="menuHandlers" project-type="discussion" :project-id="projectId" :active="active" />
    <ChatMessageReferences ref="references" :project-id="projectId" project-type="discussion" @locate="locate" />
    <TechnicalTaskDialog v-if="taskDraft" dialog-only :initial-content="taskDraft.content" @close="taskDraft = null" />
  </section>
</template>
<script setup>
import {useChatDraft} from '@/composables/useChatDraft'
import ChatRecalledMessage from './ChatRecalledMessage.vue'
import { useRecalledMessageDrafts } from '@/composables/useRecalledMessageDrafts'
import { combineRecallDraft } from '@/utils/recallDrafts'
import {quoteSpeakerMention,clearAutomaticQuoteMention} from '@/utils/quoteSpeakerMention'
import DiscussionMentionInput from './DiscussionMentionInput.vue'
import {mentionParts} from '@/utils/chatMentions'
import { screenshotPreview } from '@/utils/screenshotReferences'
import ChatMessageActions from './ChatMessageActions.vue'
import ChatMessageContextMenu from './ChatMessageContextMenu.vue'
import TechnicalRequirementsPanel from './TechnicalRequirementsPanel.vue'
import { copyTextToClipboard } from '@/utils/clipboard'
import { ElMessage, ElMessageBox } from 'element-plus'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import ChatMessageReferences from './ChatMessageReferences.vue'
import { useChatMessageInteractions } from '@/composables/useChatMessageInteractions'
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { canViewTechnicalDevelopment } from '@/utils/technicalDevelopmentAccess'
import { chatRequest } from '@/api/projectChat'
import { discussionMessagePayload } from '@/utils/discussionMessagePayload'
import { chatDayKey, chatTimestampIndexes } from '@/utils/chatLayout'
import { useChatTimeDisplay } from '@/composables/useChatTimeDisplay'
const { formatMessageTime: chatMessageTime, formatMessageDay, showMessageTime, showMessageDates } = useChatTimeDisplay()
import { formatBusinessDateTime } from '@/utils/dateTime'
import { subscribe } from '@/utils/realtimeSocket'
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
const recallDrafts = useRecalledMessageDrafts(computed(() => ['discussion', props.projectId]))
const messages = ref([]), list = ref(), input = ref(), content = ref(''), replyTo = ref(null)
const timestampIndexes = computed(() => chatTimestampIndexes(messages.value))
const references=ref(), messageMenu=ref()
const technicalPanel=ref(),technicalRoom=ref(null)
const messageInteractions=useChatMessageInteractions({projectId:computed(()=>props.projectId),projectType:computed(()=>'discussion'),messages,active:computed(()=>props.active)})
function openMessageReferences(message,event){if(message.reply||messageInteractions.stats[message.id]?.replyCount)references.value.open(message.reply?.id||message.id,event)}
const loading = ref(false), loadingEarlier = ref(false), hasEarlier = ref(false), storageReady = ref(false)
const error = ref(''), sendError = ref(''), sending = ref(false), retryPayload = ref(null), pendingNew = ref(false)
const searchOpen = ref(false), keyword = ref(''), favoritesOnly=ref(false)
const screenshotUploading=ref(false)
const mentionUsers=ref([]),mentionSelection=ref({mentionedUserIds:[],mentionAll:false})
const automaticQuoteMention=ref(null)
function selectedMentionPeople(){return mentionSelection.value.selectedUsers || (mentionSelection.value.mentionedUserIds||[]).map(id=>mentionUsers.value.find(person=>person.id===id)||{id})}
function applyQuoteMention(result){content.value=result.content;automaticQuoteMention.value=result.automatic;mentionSelection.value={selectedUsers:result.selectedUsers,mentionedUserIds:result.selectedUsers.filter(person=>!person.all&&person.id!=='__all__').map(person=>person.id),mentionAll:result.selectedUsers.some(person=>person.all||person.id==='__all__')};if(result.warning)ElMessage.warning(result.warning)}
async function quoteMessage(message){if(sending.value||retryPayload.value)return;const result=quoteSpeakerMention({content:content.value,selectedUsers:selectedMentionPeople(),automatic:automaticQuoteMention.value,message,currentUserId,users:mentionUsers.value});replyTo.value=message;applyQuoteMention(result);await nextTick();input.value?.focus()}
function cancelQuote(){if(sending.value||retryPayload.value)return;applyQuoteMention(clearAutomaticQuoteMention(content.value,selectedMentionPeople(),automaticQuoteMention.value));replyTo.value=null}
watch(replyTo,value=>{if(!value&&automaticQuoteMention.value)applyQuoteMention(clearAutomaticQuoteMention(content.value,selectedMentionPeople(),automaticQuoteMention.value))})
async function loadMentionUsers(){try{const group=await chatRequest(`${base}/group`);mentionUsers.value=[...(group.eligibleUsers||[]),...(group.invitableUsers||[]).map(person=>({...person,outside:true}))]}catch{mentionUsers.value=[]}}
const canSend = computed(() => !screenshotUploading.value && !sending.value && (!!retryPayload.value || !!content.value.trim()))
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
    const data = await chatRequest(`${base}/messages`, { params: { keyword: keyword.value.trim(), favorites_only:favoritesOnly.value || undefined }, signal: controller.signal })
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
    const data = await chatRequest(`${base}/messages`, { params: { before: messages.value[0].id, keyword: keyword.value.trim(), favorites_only:favoritesOnly.value || undefined } })
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
  const payload = discussionMessagePayload(retryPayload.value || { content: content.value.trim(), clientMessageId: newClientId(), ...mentionSelection.value, replyToId: replyTo.value?.id || null })
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
  try { await ElMessageBox.confirm('撤回后其他用户将无法查看该消息，确定撤回？','确认撤回',{type:'warning',customClass:'chat-confirm-message-box'}); await recallDrafts.remember(message); const row = await chatRequest(`${base}/messages/${message.id}/recall`, { method: 'put' }); if (!disposed) merge([row]) }
  catch (e) { if (!disposed && e !== 'cancel' && e !== 'close') error.value = e.message }
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
  favorite:message=>action(message,'favorite',!message.isFavorited),acknowledge,recall,
  ...(technicalRoom.value?{technical:message=>technicalPanel.value.append(message)}:{}),
  ...(canCreateDevelopmentTask.value ? { 'development-task': createDevelopmentTask } : {}),
}))
watch(favoritesOnly,()=>refresh(true))
watch(keyword, value => { clearTimeout(searchTimer); controller?.abort(); ++requestVersion; searchTimer = setTimeout(() => refresh(true), value ? 400 : 0) })
watch(() => props.active, active => { clearInterval(pollTimer); if (active) { loadMentionUsers();refresh(!messages.value.length); pollTimer = setInterval(() => refresh(), 5000) } else { controller?.abort(); ++requestVersion; loading.value = false } }, { immediate: true })
const unsubscribe = subscribe('chat_sessions_changed', () => { if (props.active && !sending.value) {refresh();loadMentionUsers()} })
let locatedTarget = ''
watch(() => [props.active, props.targetMessageId, loading.value, storageReady.value], ([active, id, busy, ready]) => {
  if (active && id && !busy && ready && locatedTarget !== id) { locatedTarget = id; locate(id) }
}, { flush: 'post' })
const draft=useChatDraft(computed(()=>['discussion',props.projectId]),()=>({content:content.value,mentionSelection:mentionSelection.value,replyTo:replyTo.value,automaticQuoteMention:automaticQuoteMention.value,retryPayload:retryPayload.value}),data=>{content.value=data.content;mentionSelection.value=data.mentionSelection||{mentionedUserIds:[],mentionAll:false};replyTo.value=data.replyTo||null;automaticQuoteMention.value=data.automaticQuoteMention||null;retryPayload.value=data.retryPayload||null})
onBeforeUnmount(() => { disposed = true; controller?.abort(); clearInterval(pollTimer); clearTimeout(searchTimer); unsubscribe() })
async function locate(id) {
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
.discussion-chat__message-main{display:flex;align-items:center;gap:5px}.discussion-chat__message.is-own .discussion-chat__message-main{flex-direction:row-reverse}.discussion-chat__message-main .discussion-chat__bubble{margin-left:0;max-width:calc(94% - 35px)}.discussion-chat__message:hover .chat-message-more,.discussion-chat__message:focus-within .chat-message-more{opacity:1}.discussion-mention-highlight{background:#fef3c7;color:#92400e;border-radius:3px}.discussion-chat__meta{flex-wrap:wrap}.discussion-chat__meta time{overflow-wrap:anywhere}
.discussion-chat{display:flex;flex-direction:column;height:100%;min-height:0;background:#f6f8fb;color:#334155;font-size:13px}.discussion-chat__search{display:flex;gap:8px;padding:10px;background:white}.discussion-chat__timeline{flex:1;min-height:0;overflow-y:auto;padding:16px;overflow-anchor:none}.discussion-chat__date{text-align:center;color:#94a3b8;font-size:11px;margin:12px 0}.discussion-chat__message{margin:12px 0}.discussion-chat__meta{display:flex;align-items:center;gap:8px;margin-bottom:5px;color:#64748b;font-size:11px}.discussion-chat__meta strong{font-weight:500}.discussion-chat__bubble{width:fit-content;max-width:85%;padding:10px 13px;border:1px solid #e2e8f0;border-radius:12px;background:white;overflow-wrap:anywhere}.discussion-chat__bubble p{white-space:pre-wrap;line-height:1.7;margin:0;user-select:text}.discussion-chat__bubble blockquote{margin:0 0 7px;padding:5px 8px;border-left:2px solid #94a3b8;background:#f1f5f9;color:#64748b;white-space:pre-wrap;font-size:11px}.discussion-chat__message.is-own .discussion-chat__meta,.discussion-chat__message.is-own .discussion-chat__message-actions{justify-content:flex-end}.discussion-chat__message.is-own .discussion-chat__bubble{margin-left:auto;background:#e9f0fb;border-color:#d4e0f3}.discussion-chat__message-actions{display:flex;gap:8px;opacity:0}.discussion-chat__message:hover .discussion-chat__message-actions,.discussion-chat__message:focus-within .discussion-chat__message-actions{opacity:1}.discussion-chat__message-actions .el-button{font-size:10px;color:#94a3b8}.discussion-chat__recalled,.discussion-chat__hint{text-align:center;color:#94a3b8;font-size:12px}.discussion-chat__composer{flex:none;margin:10px 14px 14px;padding:10px;border:1px solid #dfe5ee;border-radius:12px;background:white}.discussion-chat__composer :deep(.el-textarea__inner){box-shadow:none;background:#fff}.discussion-chat__footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:8px}.discussion-chat__footer>span{margin-right:auto;font-size:11px;color:#94a3b8}.discussion-chat__reply{display:flex;align-items:center;justify-content:space-between;max-height:65px;overflow:auto;padding:5px 8px;background:#f1f5f9;font-size:12px;overflow-wrap:anywhere}.discussion-chat__error{color:#b91c1c;font-size:12px;margin:5px 0}.discussion-chat__new{align-self:center}@media(max-width:600px){.discussion-chat__footer>span{display:none}.discussion-chat__bubble{max-width:94%}}
</style>

<style scoped src="./chatQuotes.css" />
