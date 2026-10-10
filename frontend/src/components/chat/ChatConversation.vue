<template>
  <section class="annotation-group" :class="{ 'annotation-group--embedded': !conversationMode, 'annotation-group--search-side': searchOpen && historyPlacement === 'side' }">
    <div class="annotation-group__main">
    <div class="group-toolbar">
      <el-popover trigger="click" placement="bottom-end" :width="340" popper-class="annotation-members-popover annotation-participants-popover">
        <template #reference><el-button text size="small" class="group-participants" :icon="User">参与人 <span class="group-member-count">{{ group.members.length }}</span></el-button></template>
        <p class="group-hint">{{ isDirect ? '仅双方可以访问此会话。' : '有项目查看权限的用户均可发言，参与人会持续收到未读提醒。' }}</p>
        <div class="group-members"><el-button v-for="member in group.members" :key="member.id" link :disabled="member.id === currentUserId" @click="startDirect(member)">{{ member.name }}</el-button></div>
        <el-select v-if="!isDirect" v-model="inviteIds" multiple filterable :teleported="false" placeholder="选择邀请用户" style="width:100%">
          <el-option v-for="user in group.eligibleUsers" :key="user.id" :value="user.id" :label="user.name" />
        </el-select>
        <el-button type="primary" size="small" v-if="!isDirect" :loading="inviting" :disabled="!inviteIds.length" @click="invite">邀请参与</el-button>
      </el-popover>
      <span class="group-toolbar-spacer" />
      <el-button text size="small" v-if="!isDirect" class="group-follow" :class="{ 'is-following': group.following }" :icon="group.following ? StarFilled : Star" :loading="followingBusy" :title="group.following ? '取消关注，不再接收普通消息未读提醒' : '关注后加入右上角收藏夹，并接收未读提醒'" :aria-label="group.following ? '取消关注' : '关注项目'" @click="toggleFollow">{{ group.following ? '已关注' : '关注' }}</el-button>
      <el-button text size="small" :icon="Search" aria-label="聊天记录" title="聊天记录" @click="openSearch">聊天记录</el-button>
      <el-button v-if="canAddToProgress" size="small" :disabled="!selected.length" @click="toProgress">转进度 {{ selected.length || '' }}</el-button>
    </div>
    <el-button v-if="unreadMentions.length" class="group-mention-jump" size="small" type="warning" @click="nextMention">{{ unreadMentions.length }} 条消息@了你</el-button>
    <div v-if="error" class="group-error" role="alert">{{ error }} <el-button link @click="search">重新加载</el-button></div>
    <ChatTimeline />
    <el-button v-if="pendingNew || viewingHistory" size="small" class="group-new" @click="returnLatest">{{ pendingNew ? `有 ${pendingNew} 条新消息` : '返回最新消息' }}</el-button>
    <ChatComposer />
    </div>
    <ChatHistorySearchPanel
      v-model:visible="searchOpen"
      :project-id="projectId"
      :project-type="projectType"
      :senders="historySenders"
      allow-files
      :placement="historyPlacement"
      @locate="onSearchLocate"
    />
  </section>
</template>

<script setup>
import { provide, computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Paperclip, User, Star, StarFilled, Search } from '@element-plus/icons-vue'
import { annotationChatRequest, directChatRequest, chatRequest, createProjectChatMessage, favoriteProjectChatMessage, unfavoriteProjectChatMessage,
  acknowledgeProjectChatMessage, unacknowledgeProjectChatMessage, getProjectChatAttachmentBlob } from '@/api/projectChat'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import ChatTimeline from './ChatTimeline.vue'
import ChatComposer from './ChatComposer.vue'
import ChatHistorySearchPanel from '@/components/chat/ChatHistorySearchPanel.vue'
import { subscribe, watchAnnotationChat } from '@/utils/realtimeSocket'
import { copyTextToClipboard } from '@/utils/clipboard'
import { formatBusinessDateTime as formatDateTime } from '@/utils/dateTime'
import { mentionParts as splitMentionParts } from '@/utils/chatMentions'

const props = defineProps({
  projectType: { type: String, default: 'annotation' },
  targetMessageId: { type: String, default: '' },
  projectId: [String, Number],
  active: Boolean,
  conversationMode: Boolean,
  canAddToProgress: Boolean,
  historyPlacement: { type: String, default: 'overlay' },
})
const isDirect = computed(() => props.projectType === 'direct')
const request = (...args) => (isDirect.value ? directChatRequest : annotationChatRequest)(...args)
const emit = defineEmits(['add-to-progress', 'unread'])
const currentUserId = localStorage.getItem('user_id') || ''
// 局域网 HTTP 下 randomUUID 可能不可用，getRandomValues 仍可生成标准 UUID。
const newMessageId = () => {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
const group = reactive({ members: [], eligibleUsers: [], following: false })
const messages = ref([]), list = ref(null), input = ref(null), content = ref(''), replyTo = ref(null)
const composer = ref(null), mentionMenu = ref(null), mentionOpen = ref(false), mentionQuery = ref(''), mentionIndex = ref(0), mentionStyle = ref({})
const mentionListId = `mention-${newMessageId()}`
const mentionCandidates = computed(() => group.eligibleUsers.filter(u => u.name.toLocaleLowerCase().includes(mentionQuery.value.toLocaleLowerCase())))
let mentionTrigger = -1
const selected = ref([]), selectionMessage = ref(null), inviteIds = ref([]), mentionIds = ref([])
const files = ref([]), sending = ref(false), retryPayload = ref(null), sendError = ref(''), composing = ref(false)
const inviting = ref(false), followingBusy = ref(false), searchOpen = ref(false)
const loading = ref(false), loadingEarlier = ref(false), hasEarlier = ref(false), error = ref('')
const pendingNew = ref(0), viewingHistory = ref(false), highlighted = ref('')
const imageUrls = reactive({}), imageErrors = reactive({}), imageRequests = new Set()
const historySenders = computed(() => group.eligibleUsers.map(user => ({ id: user.id, name: user.name })))
const canSend = computed(() => !sending.value && (retryPayload.value || (!files.value.some(f => f.status !== 'ready') && (!!content.value.trim() || files.value.length > 0))))
const detail = e => e?.detail || e?.message || '操作失败，请重试'
const sizeLabel = bytes => bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`
let disposed = false, generation = 0, searchController, searchTimer, syncTimer, syncing = false, syncAgain = false, unwatch, observer, readTimer
let lastRead = 0, readBusy = false
const visibleMessages = new Map(), observedElements = new WeakSet(), cleanup = []
const atBottom = () => !!list.value && list.value.scrollHeight - list.value.scrollTop - list.value.clientHeight < 45
const bottom = async () => { await nextTick(); if (list.value) list.value.scrollTop = list.value.scrollHeight; pendingNew.value = 0 }


const { sessions: followed, refresh: refreshSessions } = useAnnotationFollowed()
const seenMentions = ref([])
const session = computed(() => followed.value.find(s => s.key === `${props.projectType}:${props.projectId}`))
const unreadMentions = computed(() => (session.value?.mentionMessageIds || []).filter(id => !seenMentions.value.includes(id)))
const mentionsMe = message => !message.recalledAt && (message.mentions || []).some(m => m.mentionedUserId === currentUserId)
function mentionParts(message) {
  return splitMentionParts(message, currentUserId)
}
async function nextMention() {
  const id = unreadMentions.value[0]
  if (!id) return
  await locate(id)
  const message = messages.value.find(m => m.id === id)
  if (!message || !props.active || !document.hasFocus()) return
  try {
    await request(props.projectId, 'read', { method: 'put', data: { messageId: id } })
    seenMentions.value.push(id); lastRead = Math.max(lastRead, message.sequenceNo); await refreshSessions()
  } catch (e) { ElMessage.error(detail(e)) }
}
async function startDirect(member) {
  try {
    const data = await chatRequest('direct/conversations', { method: 'post', data: { userId: member.id } })
    useProjectChatDock().openChat({ projectId: data.id, projectType: 'direct', title: data.title, subtitle: data.subtitle })
    await refreshSessions()
  } catch (e) { ElMessage.error(detail(e)) }
}
watch(() => props.targetMessageId, id => { if (id) locate(id) })

async function loadGroup() {
  try { const data = await request(props.projectId, 'group'); if (!disposed) { Object.assign(group, data); lastRead = Math.max(lastRead, data.lastReadSequence || 0) } } catch (e) { error.value = detail(e) }
}
function merge(rows) {
  const merged = new Map(messages.value.map(m => [m.id, m]))
  rows.forEach(m => merged.set(m.id, m))
    messages.value = [...merged.values()].sort((a, b) => a.sequenceNo - b.sequenceNo)
  selected.value = selected.value.filter(id => merged.has(id) && !merged.get(id).recalledAt)
  if (replyTo.value && merged.get(replyTo.value.id)?.recalledAt) replyTo.value = null
  const validImages = new Set(messages.value.flatMap(m => m.attachments || []).map(f => f.id))
  Object.keys(imageUrls).forEach(id => { if (!validImages.has(id)) { URL.revokeObjectURL(imageUrls[id]); delete imageUrls[id] } })
  rows.filter(m => !m.recalledAt).forEach(m => m.attachments?.filter(f => f.contentType.startsWith('image/')).forEach(loadImage))
}
async function search() {
  clearTimeout(searchTimer)
  searchController?.abort()
  searchController = new AbortController()
  const version = ++generation
  loading.value = true; error.value = ''; viewingHistory.value = false
  try {
    const data = await request(props.projectId, 'timeline', { signal: searchController.signal })
    if (version !== generation || disposed) return
    messages.value = []; visibleMessages.clear(); merge(data.items); hasEarlier.value = data.hasMore
    await bottom()
  } catch (e) { if (version === generation && !searchController.signal.aborted) error.value = detail(e) }
  finally { if (version === generation) loading.value = false }
}
async function loadEarlier() {
  if (loadingEarlier.value || !messages.value.length) return
  const version = generation, height = list.value.scrollHeight, top = list.value.scrollTop
  loadingEarlier.value = true
  try {
    const data = await request(props.projectId, 'timeline', { params: { before: messages.value[0].sequenceNo } })
    if (version !== generation || disposed) return
    merge(data.items); hasEarlier.value = data.hasMore
    await nextTick(); if (list.value) list.value.scrollTop = top + list.value.scrollHeight - height
  } catch (e) { error.value = detail(e) } finally { loadingEarlier.value = false }
}
async function sync() {
  if (disposed || !props.projectId || loading.value) return
  if (syncing) { syncAgain = true; return }
  syncing = true
  const version = generation, wasBottom = atBottom()
  try {
    // 更新全部已加载消息，补偿历史消息撤回、引用摘要和收到状态的变化。
    const ids = messages.value.map(m => m.id)
    for (let i = 0; i < ids.length; i += 200) {
      const data = await request(props.projectId, 'refresh', { method: 'post', data: { messageIds: ids.slice(i, i + 200) } })
      if (version !== generation || disposed) return
      merge(data.items)
    }
    if (!viewingHistory.value) {
      let more = true
      while (more) {
        const after = messages.value.at(-1)?.sequenceNo || 0
        const data = await request(props.projectId, 'timeline', { params: { after, limit: 100 } })
        if (version !== generation || disposed) return
        const incoming = data.items.filter(m => !messages.value.some(existing => existing.id === m.id))
        if (!props.active) incoming.filter(m => !m.recalledAt && m.senderUserId !== currentUserId).forEach(() => emit('unread'))
        merge(data.items); more = data.hasMore && data.items.length > 0
        if (!wasBottom || !props.active) pendingNew.value += incoming.length
      }
    }
    if (wasBottom && !viewingHistory.value && props.active) await bottom()
    error.value = ''
  } catch (e) { error.value = detail(e) }
  finally { syncing = false; if (syncAgain) { syncAgain = false; sync() } }
}
async function returnLatest() { await search(); await bottom() }
async function locate(id) {
  if (!messages.value.some(m => m.id === id)) {
    const version = ++generation
    searchController?.abort()
    const controller = new AbortController(); searchController = controller
    try {
      const data = await request(props.projectId, 'timeline', { params: { around: id }, signal: controller.signal })
      if (version !== generation || disposed) return
      messages.value = []; visibleMessages.clear(); merge(data.items); hasEarlier.value = true; viewingHistory.value = true
    } catch (e) { if (!controller.signal.aborted) ElMessage.error(detail(e)); return }
  }
  await nextTick()
  list.value?.querySelector(`[data-message-id="${id}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  highlighted.value = id
  setTimeout(() => { highlighted.value = '' }, 1800)
}
function observeMessage(el) {
  if (el && observer && !observedElements.has(el)) { observedElements.add(el); observer.observe(el) }
}
function scheduleRead() { clearTimeout(readTimer); readTimer = setTimeout(markRead, 350) }
async function markRead() {
  if (!props.active || document.visibilityState !== 'visible' || !document.hasFocus() || readBusy || (!isDirect.value && unreadMentions.value.length > 0)) return
  const visible = [...visibleMessages.entries()].filter(([id]) => messages.value.some(m => m.id === id)).sort((a, b) => b[1] - a[1])[0]
  if (!visible || visible[1] <= lastRead) return
  readBusy = true
  try { await request(props.projectId, 'read', { method: 'put', data: { messageId: visible[0] } }); lastRead = visible[1]; await loadGroup() }
  catch { /* 下次进入前台或轮询时重试，不提前清除未读。 */ }
  finally { readBusy = false }
}
function onScroll() { if (atBottom()) pendingNew.value = 0; scheduleRead() }
async function toggleFollow() {
  followingBusy.value = true
  try { await request(props.projectId, 'following', { method: 'put', data: { following: !group.following } }); await loadGroup() }
  catch (e) { ElMessage.error(detail(e)) } finally { followingBusy.value = false }
}
async function invite() {
  inviting.value = true
  try { const data = await request(props.projectId, 'invitations', { method: 'post', data: { userIds: inviteIds.value } }); inviteIds.value = []; await loadGroup(); ElMessage.success(`已邀请 ${data.invitedCount} 人；已关注或主动取消关注的用户保持原状态`) }
  catch (e) { ElMessage.error(detail(e)) } finally { inviting.value = false }
}
async function copy(message) { await copyTextToClipboard(message.content || (message.attachments || []).map(f => f.originalName).join('\n')); ElMessage.success('已复制') }
async function favorite(message) {
  try { const result = await (message.isFavorited ? unfavoriteProjectChatMessage : favoriteProjectChatMessage)(message.id); Object.assign(message, result) } catch (e) { ElMessage.error(detail(e)) }
}
async function acknowledge(message) {
  try { const result = await (message.isAcknowledged ? unacknowledgeProjectChatMessage : acknowledgeProjectChatMessage)(message.id); Object.assign(message, result) } catch (e) { ElMessage.error(detail(e)) }
}
async function recall(message) {
  try {
    await ElMessageBox.confirm(message.senderUserId === currentUserId ? '撤回后其他用户将无法查看正文和附件，确定撤回？' : '确定以管理员身份移除此消息？', '确认操作', { type: 'warning', customClass: 'chat-confirm-message-box' })
    const data = await request(props.projectId, `messages/${message.id}/recall`, { method: 'post' }); merge([data]); await sync()
  } catch (e) { if (e !== 'cancel' && e !== 'close') ElMessage.error(detail(e)) }
}
function toProgress() {
  const rows = messages.value.filter(m => selected.value.includes(m.id) && !m.recalledAt && m.content)
  if (rows.reduce((sum, m) => sum + m.content.length + m.senderName.length + 6, 0) > 10000) return ElMessage.warning('所选消息超过具体进度10000字限制')
  emit('add-to-progress', rows)
}
async function fileBlob(file) {
  try { return await request(props.projectId, `files/${file.id}`, { responseType: 'blob' }) }
  catch (e) { if (file.contentType.startsWith('image/')) return getProjectChatAttachmentBlob(file.id); throw e }
}
async function loadImage(file) {
  if (imageUrls[file.id] || imageRequests.has(file.id)) return
  imageRequests.add(file.id); delete imageErrors[file.id]
  try { const blob = await fileBlob(file); if (!disposed && messages.value.some(m => !m.recalledAt && m.attachments?.some(f => f.id === file.id))) imageUrls[file.id] = URL.createObjectURL(blob) }
  catch { imageErrors[file.id] = true } finally { imageRequests.delete(file.id) }
}
async function download(file) {
  try { const blob = await fileBlob(file), url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = file.originalName; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) }
  catch (e) { ElMessage.error(detail(e)) }
}
function chooseFile(file, uploadFiles) { addFiles([file.raw]); uploadFiles.splice(0) }
function addFiles(chosen) {
  if (sending.value || retryPayload.value) return
  for (const file of chosen) {
    if (files.value.length >= 9) { ElMessage.warning('每条消息最多9个附件'); break }
    const max = file.type.startsWith('image/') ? 10 : 20
    if (!file.size || file.size > max * 1024 * 1024) { ElMessage.warning(`文件不能为空，图片最多10MB，其他文件最多20MB：${file.name}`); continue }
    const row = reactive({ key: newMessageId(), file, status: 'uploading', data: null, error: '' }); files.value.push(row); uploadFile(row)
  }
}
async function uploadFile(row) {
  row.status = 'uploading'; row.error = ''
  const data = new FormData(); data.append('file', row.file)
  try { row.data = await request(props.projectId, 'files', { method: 'post', data }); row.status = 'ready' }
  catch (e) { row.status = 'failed'; row.error = detail(e) }
}
function removeFile(file) { files.value = files.value.filter(f => f.key !== file.key) }
function paste(event) { const images = [...(event.clipboardData?.files || [])].filter(f => f.type.startsWith('image/')); if (images.length) { if (!event.clipboardData.getData('text/plain')) event.preventDefault(); addFiles(images) } }
function onKeydown(event) {
  if (event.isComposing || composing.value || event.keyCode === 229) return
  if (mentionOpen.value) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeMention(); return }
    if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault()
      const count = mentionCandidates.value.length
      if (count) mentionIndex.value = (mentionIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + count) % count
      nextTick(() => mentionMenu.value?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' }))
      return
    }
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); if (mentionCandidates.value.length) selectMention(mentionCandidates.value[mentionIndex.value]); return }
    if (event.key === 'Tab') closeMention()
  }
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !composing.value && event.keyCode !== 229) { event.preventDefault(); send() }
}
function closeMention() { mentionOpen.value = false; mentionTrigger = -1 }
function finishComposition() { composing.value = false; nextTick(onInput) }
async function onInput() {
  if (composing.value || isDirect.value) return
  await nextTick()
  const textarea = input.value?.textarea, cursor = textarea?.selectionStart || 0
  const match = content.value.slice(0, cursor).match(/(?:^|[^A-Za-z0-9@])@([^\s@]*)$/u)
  if (!match || textarea.selectionStart !== textarea.selectionEnd) { closeMention(); return }
  mentionTrigger = cursor - match[1].length - 1
  mentionQuery.value = match[1]; mentionIndex.value = 0; mentionOpen.value = true
  positionMention()
}
function positionMention() {
  const textarea = input.value?.textarea
  if (!mentionOpen.value || !textarea || !composer.value) return
  // 镜像文本的字体、换行和滚动位置，将候选面板锚定到当前 @ 所在行。
  const mirror = document.createElement('div'), style = getComputedStyle(textarea)
  for (const key of ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'padding', 'border', 'boxSizing', 'wordBreak', 'tabSize']) mirror.style[key] = style[key]
  Object.assign(mirror.style, { position: 'fixed', visibility: 'hidden', whiteSpace: 'pre-wrap', overflowWrap: 'break-word', width: `${textarea.clientWidth}px`, left: '0', top: '0' })
  mirror.textContent = content.value.slice(0, mentionTrigger)
  const anchor = document.createElement('span'); anchor.textContent = content.value.slice(mentionTrigger) || '@'; mirror.append(anchor); document.body.append(mirror)
  const field = textarea.getBoundingClientRect(), root = composer.value.getBoundingClientRect()
  const x = field.left + anchor.offsetLeft - textarea.scrollLeft, y = Math.max(field.top, field.top + anchor.offsetTop - textarea.scrollTop)
  mirror.remove()
  const width = Math.min(280, root.width - 16)
  mentionStyle.value = { width: `${width}px`, left: `${Math.max(8, Math.min(x - root.left, root.width - width - 8))}px`, bottom: `${root.bottom - y + 6}px`, maxHeight: `${Math.max(60, Math.min(250, y - 12))}px` }
}
async function selectMention(user) {
  if (mentionTrigger < 0) return
  if (!mentionIds.value.includes(user.id) && mentionIds.value.length >= 20) { ElMessage.warning('每条消息最多提及20人'); return }
  const cursor = input.value.textarea.selectionStart, text = `@${user.name} `, end = mentionTrigger + text.length
  content.value = content.value.slice(0, mentionTrigger) + text + content.value.slice(cursor)
  if (!mentionIds.value.includes(user.id)) mentionIds.value.push(user.id)
  closeMention(); await nextTick(); input.value.focus(); input.value.textarea.setSelectionRange(end, end)
}
async function send() {
  if (!canSend.value) return
  sending.value = true; sendError.value = ''
  closeMention()
  const payload = retryPayload.value || { content: content.value, mentionedUserIds: mentionIds.value.filter(id => group.eligibleUsers.some(u => u.id === id && content.value.includes(`@${u.name} `))), attachmentIds: files.value.map(f => f.data.id), replyToMessageId: replyTo.value?.id || null, clientMessageId: newMessageId() }
  try {
    const message = await createProjectChatMessage(props.projectId, payload, props.projectType)
    retryPayload.value = null; content.value = ''; files.value = []; replyTo.value = null; mentionIds.value = []
    if (viewingHistory.value) await search()
    merge([message]); await bottom(); await loadGroup()
  } catch (e) { retryPayload.value = payload; sendError.value = detail(e) }
  finally { sending.value = false; nextTick(() => input.value?.focus()) }
}
async function cancelRetry() {
  if (!retryPayload.value || sending.value) return
  sending.value = true
  try {
    const result = await request(props.projectId, `sent/${retryPayload.value.clientMessageId}`)
    if (result.message) {
      merge([result.message]); content.value = ''; files.value = []; replyTo.value = null; mentionIds.value = []
      ElMessage.success('已确认上一条消息发送成功')
    }
    retryPayload.value = null; sendError.value = ''
  } catch (e) { sendError.value = `暂时无法确认发送结果，请重试：${detail(e)}` }
  finally { sending.value = false }
}
function foreground() { scheduleRead(); sync() }
watch(() => props.active, active => { if (active) { sync(); scheduleRead() } else closeMention() })
onMounted(async () => {
  observer = new IntersectionObserver(entries => { entries.forEach(entry => { const id = entry.target.dataset.messageId; if (entry.isIntersecting && entry.intersectionRatio >= 0.5) visibleMessages.set(id, Number(entry.target.dataset.sequence)); else visibleMessages.delete(id) }); scheduleRead() }, { root: list.value, threshold: [0, 0.5, 1] })
  if (!isDirect.value) unwatch = watchAnnotationChat(props.projectId)
  cleanup.push(subscribe(isDirect.value ? 'direct_chat_changed' : 'annotation_chat_changed', event => { if (event.projectId !== String(props.projectId)) return; if (event.kind === 'members' || event.kind === 'message') loadGroup(); if (event.kind !== 'state') sync() }))
  cleanup.push(subscribe('connected', () => { sync(); loadGroup() }))
  cleanup.push(subscribe('chat_message_acknowledgement', event => { if (event.projectId === String(props.projectId)) sync() }))
  document.addEventListener('visibilitychange', foreground); window.addEventListener('focus', foreground)
  window.addEventListener('resize', closeMention)
  await loadGroup(); await search()
  if (props.targetMessageId) await locate(props.targetMessageId)
  if (!disposed) syncTimer = setInterval(() => { sync(); loadGroup(); scheduleRead() }, 12000)
})
onBeforeUnmount(() => {
  disposed = true; ++generation; searchController?.abort(); clearTimeout(searchTimer); clearTimeout(readTimer); clearInterval(syncTimer)
  unwatch?.(); cleanup.forEach(fn => fn()); observer?.disconnect()
  document.removeEventListener('visibilitychange', foreground); window.removeEventListener('focus', foreground)
  window.removeEventListener('resize', closeMention)
  Object.values(imageUrls).forEach(URL.revokeObjectURL)
})
function openSearch() { searchOpen.value = !searchOpen.value }
function onSearchLocate(messageId) { return locate(messageId) }
provide('chatController', { props, messages, list, hasEarlier, loadingEarlier, loadEarlier, loading, currentUserId, selected, selectionMessage, highlighted, observeMessage, onScroll, formatDateTime, locate, imageUrls, imageErrors, sizeLabel, loadImage, download, copy, replyTo, favorite, acknowledge, recall, mentionsMe, mentionParts, composer, sending, retryPayload, files, chooseFile, uploadFile, removeFile, input, content, mentionOpen, mentionListId, mentionCandidates, mentionIndex, onInput, closeMention, onKeydown, composing, finishComposition, paste, mentionMenu, mentionStyle, selectMention, cancelRetry, canSend, send, sendError, isDirect })
defineExpose({ openSearch, locate, toggleFilters: openSearch })
</script>

<style scoped src="./chatConversation.css" />
<style>
.el-overlay:has(.chat-confirm-message-box){z-index:100001!important}
.annotation-members-popover{max-width:calc(100vw - 32px)!important;max-height:min(560px,calc(100vh - 120px));overflow-y:auto}
/* 邀请用户的下拉层留在参与人弹窗内，弹窗不能裁切下拉选项。 */
.annotation-members-popover.annotation-participants-popover{overflow:visible}
</style>
<style scoped>
.group-mention-jump{position:absolute;right:12px;top:48px;z-index:2}
</style>
