<template>
  <section class="annotation-group" :class="{ 'annotation-group--embedded': !conversationMode }">
    <div class="group-toolbar">
      <el-popover trigger="click" placement="bottom-end" :width="340" popper-class="annotation-members-popover">
        <template #reference><el-button text size="small" class="group-participants" :icon="User">参与人 <span class="group-member-count">{{ group.members.length }}</span></el-button></template>
        <p class="group-hint">有项目查看权限的用户均可发言，参与人会持续收到未读提醒。</p>
        <div class="group-members"><el-tag v-for="member in group.members" :key="member.id">{{ member.name }}</el-tag></div>
        <el-select v-model="inviteIds" multiple filterable placeholder="选择邀请用户" style="width:100%">
          <el-option v-for="user in group.eligibleUsers" :key="user.id" :value="user.id" :label="user.name" />
        </el-select>
        <el-button type="primary" size="small" :loading="inviting" :disabled="!inviteIds.length" @click="invite">邀请参与</el-button>
      </el-popover>
      <span class="group-toolbar-spacer" />
      <el-button text size="small" class="group-follow" :class="{ 'is-following': group.following }" :icon="group.following ? StarFilled : Star" :loading="followingBusy" :title="group.following ? '取消关注，不再接收普通消息未读提醒' : '关注后加入右上角收藏夹，并接收未读提醒'" :aria-label="group.following ? '取消关注' : '关注项目'" @click="toggleFollow">{{ group.following ? '已关注' : '关注' }}</el-button>
      <el-popover v-model:visible="filtersVisible" trigger="click" placement="bottom-end" :width="340" popper-class="annotation-members-popover">
        <template #reference><el-button text size="small" :icon="Search" aria-label="搜索消息" title="搜索消息">{{ filterCount || '' }}</el-button></template>
        <div class="group-filters">
          <el-input v-model="filters.keyword" clearable placeholder="搜索消息内容" @keyup.enter="search" />
          <el-select v-model="filters.sender" clearable filterable placeholder="发送人" @change="search"><el-option v-for="u in group.eligibleUsers" :key="u.id" :value="u.id" :label="u.name" /></el-select>
          <el-date-picker v-model="filters.dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" @change="search" />
          <el-checkbox v-model="filters.favorites" @change="search">只看收藏</el-checkbox>
          <div><el-button size="small" type="primary" @click="search">查询</el-button><el-button size="small" @click="resetSearch">重置</el-button><el-button size="small" @click="filtersVisible=false">关闭</el-button></div>
        </div>
      </el-popover>
      <el-button v-if="canAddToProgress" size="small" :disabled="!selected.length" @click="toProgress">转进度 {{ selected.length || '' }}</el-button>
    </div>
    <div v-if="error" class="group-error" role="alert">{{ error }} <el-button link @click="search">重新加载</el-button></div>
    <div ref="list" class="group-timeline" @scroll="onScroll">
      <el-button v-if="hasEarlier" class="group-earlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="group-hint">正在加载消息…</div>
      <el-empty v-if="!loading && !messages.length" description="暂无消息，直接开始项目沟通" :image-size="50" />
      <article v-for="message in messages" :key="message.id" :ref="el => observeMessage(el, message)" :data-message-id="message.id" :data-sequence="message.sequenceNo"
        class="group-message" :class="{ 'group-message--own': message.senderUserId === currentUserId, 'group-message--highlight': highlighted === message.id }">
        <div v-if="message.recalledAt" class="group-recalled">{{ message.recallLabel }}</div>
        <template v-else>
          <div class="group-message-meta"><el-checkbox v-if="canAddToProgress && message.content" v-model="selected" :value="message.id" :label="message.id"><span class="sr-only">选择消息</span></el-checkbox><strong>{{ message.senderName }}</strong><time>{{ formatDateTime(message.createdAt) }}</time></div>
          <div class="group-bubble">
            <button v-if="message.reply" class="group-reply" @click="locate(message.reply.id)">{{ message.reply.senderName }}：{{ message.reply.content }}</button>
            <p v-if="message.content" class="group-content" @contextmenu="selectionMessage=message">{{ message.content }}</p>
            <div v-if="message.mentions?.some(m => !message.content?.includes(`@${m.mentionedUserName}`))" class="group-mentions">{{ message.mentions.filter(m => !message.content?.includes(`@${m.mentionedUserName}`)).map(m => `@${m.mentionedUserName}`).join(' ') }}</div>
            <div v-for="file in message.attachments" :key="file.id" class="group-file">
              <el-image v-if="file.contentType.startsWith('image/') && imageUrls[file.id]" :src="imageUrls[file.id]" :preview-src-list="[imageUrls[file.id]]" preview-teleported fit="contain" />
              <el-button v-else link type="primary" @click="download(file)">{{ file.originalName }} · {{ sizeLabel(file.fileSize) }}</el-button>
              <el-button v-if="file.contentType.startsWith('image/') && imageErrors[file.id]" link @click="loadImage(file)">重新加载图片</el-button>
            </div>
          </div>
          <div class="group-message-actions">
            <el-button link size="small" @click="copy(message)">复制</el-button>
            <el-button link size="small" @click="replyTo=message">引用</el-button>
            <el-button link size="small" @click="favorite(message)">{{ message.isFavorited ? '取消收藏' : '收藏' }}</el-button>
            <el-button v-if="message.senderUserId !== currentUserId" link size="small" :title="(message.acknowledgements || []).map(a => a.userName).join('、')" @click="acknowledge(message)">{{ message.isAcknowledged ? '取消收到' : '收到' }}{{ message.acknowledgementCount ? ` (${message.acknowledgementCount})` : '' }}</el-button>
            <el-button v-if="message.canRecall" link size="small" type="danger" @click="recall(message)">{{ message.senderUserId === currentUserId ? '撤回' : '移除' }}</el-button>
          </div>
        </template>
      </article>
    </div>
    <el-button v-if="pendingNew || viewingHistory" size="small" class="group-new" @click="returnLatest">{{ pendingNew ? `有 ${pendingNew} 条新消息` : '返回最新消息' }}</el-button>
    <div ref="composer" class="group-composer">
      <div v-if="replyTo" class="group-compose-reply">回复 {{ replyTo.senderName }}：{{ replyTo.content || '[附件]' }}<el-button link :disabled="sending || !!retryPayload" @click="replyTo=null">取消引用</el-button></div>
      <div class="group-compose-tools">
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip" :on-change="chooseFile"><el-button text size="small" :icon="Paperclip" :disabled="sending || !!retryPayload" title="发送图片或文件">图片 / 文件</el-button></el-upload>
      </div>
      <div v-if="files.length" class="group-file-queue"><div v-for="file in files" :key="file.key">{{ file.file.name }} · {{ file.status === 'uploading' ? '上传中…' : file.status === 'failed' ? '上传失败' : '待发送' }}<el-button v-if="file.status==='failed'" link @click="uploadFile(file)">重试</el-button><el-button link :disabled="sending || !!retryPayload" @click="removeFile(file)">移除</el-button><span v-if="file.error" class="group-error">{{ file.error }}</span></div></div>
      <el-input ref="input" v-model="content" type="textarea" :rows="3" resize="none" maxlength="10000" :disabled="sending || !!retryPayload" placeholder="输入消息，@ 提及用户" :aria-expanded="mentionOpen" aria-autocomplete="list" :aria-controls="mentionOpen ? mentionListId : undefined" :aria-activedescendant="mentionOpen && mentionCandidates.length ? `${mentionListId}-${mentionIndex}` : undefined" @input="onInput" @click="onInput" @keyup.left="onInput" @keyup.right="onInput" @scroll.capture="closeMention" @blur="closeMention" @keydown="onKeydown" @compositionstart="composing=true; closeMention()" @compositionend="finishComposition" @paste="paste" />
      <div v-if="mentionOpen" :id="mentionListId" ref="mentionMenu" class="group-mention-menu" :style="mentionStyle" role="listbox" aria-label="选择提及用户" @mousedown.prevent>
        <div class="group-mention-heading">提及用户<span>↑↓ 选择 · Enter 确认</span></div>
        <div class="group-mention-options">
          <button v-for="(user, index) in mentionCandidates" :id="`${mentionListId}-${index}`" :key="user.id" type="button" role="option" :aria-selected="index === mentionIndex" :class="{ 'is-active': index === mentionIndex }" @mouseenter="mentionIndex=index" @click="selectMention(user)"><span class="group-mention-avatar">{{ user.name.slice(0, 1) }}</span><span>{{ user.name }}</span></button>
          <div v-if="!mentionCandidates.length" class="group-mention-empty">没有匹配的用户</div>
        </div>
      </div>
      <div class="group-compose-footer"><span>Enter发送 · Shift+Enter换行</span><el-button v-if="retryPayload" size="small" @click="cancelRetry">继续编辑</el-button><el-button type="primary" size="small" :loading="sending" :disabled="!canSend" @click="send">{{ retryPayload ? '发送失败，重试' : '发送' }}</el-button></div>
      <div v-if="sendError" class="group-error" role="alert">{{ sendError }}</div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Paperclip, User, Star, StarFilled, Search } from '@element-plus/icons-vue'
import { annotationChatRequest as request, createProjectChatMessage, favoriteProjectChatMessage, unfavoriteProjectChatMessage,
  acknowledgeProjectChatMessage, unacknowledgeProjectChatMessage, getProjectChatAttachmentBlob } from '@/api/projectChat'
import { subscribe, watchAnnotationChat } from '@/utils/realtimeSocket'
import { copyTextToClipboard } from '@/utils/clipboard'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const props = defineProps({ projectId: [String, Number], active: Boolean, conversationMode: Boolean, canAddToProgress: Boolean })
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
const inviting = ref(false), followingBusy = ref(false), filtersVisible = ref(false)
const filters = reactive({ keyword: '', sender: '', dates: [], favorites: false })
const loading = ref(false), loadingEarlier = ref(false), hasEarlier = ref(false), error = ref('')
const pendingNew = ref(0), viewingHistory = ref(false), highlighted = ref('')
const imageUrls = reactive({}), imageErrors = reactive({}), imageRequests = new Set()
const filterCount = computed(() => [filters.keyword.trim(), filters.sender, filters.dates?.length, filters.favorites].filter(Boolean).length)
const canSend = computed(() => !sending.value && !files.value.some(f => f.status !== 'ready') && (!!content.value.trim() || files.value.length > 0))
const detail = e => e?.detail || e?.message || '操作失败，请重试'
const sizeLabel = bytes => bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`
let disposed = false, generation = 0, searchController, searchTimer, syncTimer, syncing = false, syncAgain = false, unwatch, observer, readTimer
let lastRead = 0, readBusy = false
const visibleMessages = new Map(), observedElements = new WeakSet(), cleanup = []
const params = () => ({ keyword: filters.keyword.trim(), sender_user_id: filters.sender || undefined, favorites_only: filters.favorites,
  date_from: filters.dates?.[0] ? `${filters.dates[0]}T00:00:00` : undefined, date_to: filters.dates?.[1] ? `${filters.dates[1]}T23:59:59.999999` : undefined })
const atBottom = () => !!list.value && list.value.scrollHeight - list.value.scrollTop - list.value.clientHeight < 45
const bottom = async () => { await nextTick(); if (list.value) list.value.scrollTop = list.value.scrollHeight; pendingNew.value = 0 }

async function loadGroup() {
  try { const data = await request(props.projectId, 'group'); if (!disposed) Object.assign(group, data) } catch (e) { error.value = detail(e) }
}
function merge(rows) {
  const merged = new Map(messages.value.map(m => [m.id, m]))
  rows.forEach(m => merged.set(m.id, m))
    messages.value = [...merged.values()].filter(m => !(filters.keyword.trim() && m.recalledAt) && (!filters.favorites || m.isFavorited)).sort((a, b) => a.sequenceNo - b.sequenceNo)
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
    const data = await request(props.projectId, 'timeline', { params: params(), signal: searchController.signal })
    if (version !== generation || disposed) return
    messages.value = []; visibleMessages.clear(); merge(data.items); hasEarlier.value = data.hasMore
    await bottom()
  } catch (e) { if (version === generation && !searchController.signal.aborted) error.value = detail(e) }
  finally { if (version === generation) loading.value = false }
}
function resetSearch() { Object.assign(filters, { keyword: '', sender: '', dates: [], favorites: false }); return search() }
watch(() => filters.keyword, value => { clearTimeout(searchTimer); if (!value) search(); else searchTimer = setTimeout(search, 400) })
async function loadEarlier() {
  if (loadingEarlier.value || !messages.value.length) return
  const version = generation, height = list.value.scrollHeight, top = list.value.scrollTop
  loadingEarlier.value = true
  try {
    const data = await request(props.projectId, 'timeline', { params: { ...params(), before: messages.value[0].sequenceNo } })
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
        const data = await request(props.projectId, 'timeline', { params: { ...params(), after, limit: 100 } })
        if (version !== generation || disposed) return
        const count = data.items.filter(m => !messages.value.some(existing => existing.id === m.id)).length
        merge(data.items); more = data.hasMore && data.items.length > 0
        if (!wasBottom || !props.active) pendingNew.value += count
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
    ++generation; searchController?.abort()
    try { const data = await request(props.projectId, 'timeline', { params: { around: id } }); messages.value = []; merge(data.items); hasEarlier.value = true; viewingHistory.value = true } catch (e) { ElMessage.error(detail(e)); return }
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
  if (!props.active || document.visibilityState !== 'visible' || !document.hasFocus() || readBusy || filterCount.value || viewingHistory.value) return
  const visible = [...visibleMessages.entries()].filter(([id]) => messages.value.some(m => m.id === id)).sort((a, b) => b[1] - a[1])[0]
  if (!visible || visible[1] <= lastRead) return
  readBusy = true
  try { await request(props.projectId, 'read', { method: 'put', data: { messageId: visible[0] } }); lastRead = visible[1] }
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
    await ElMessageBox.confirm(message.senderUserId === currentUserId ? '撤回后其他用户将无法查看正文和附件，确定撤回？' : '确定以管理员身份移除此消息？', '确认操作', { type: 'warning' })
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
  if (composing.value) return
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
    const message = await createProjectChatMessage(props.projectId, payload, 'annotation')
    retryPayload.value = null; content.value = ''; files.value = []; replyTo.value = null; mentionIds.value = []
    if (filterCount.value || viewingHistory.value) await resetSearch()
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
  unwatch = watchAnnotationChat(props.projectId)
  cleanup.push(subscribe('annotation_chat_changed', event => { if (event.projectId !== String(props.projectId)) return; if (event.kind === 'members' || event.kind === 'message') loadGroup(); if (event.kind !== 'state') sync() }))
  cleanup.push(subscribe('connected', () => { sync(); loadGroup() }))
  cleanup.push(subscribe('chat_message_acknowledgement', event => { if (event.projectId === String(props.projectId)) sync() }))
  document.addEventListener('visibilitychange', foreground); window.addEventListener('focus', foreground)
  window.addEventListener('resize', closeMention)
  await Promise.all([loadGroup(), search()])
  if (!disposed) syncTimer = setInterval(() => { sync(); loadGroup(); scheduleRead() }, 12000)
})
onBeforeUnmount(() => {
  disposed = true; ++generation; searchController?.abort(); clearTimeout(searchTimer); clearTimeout(readTimer); clearInterval(syncTimer)
  unwatch?.(); cleanup.forEach(fn => fn()); observer?.disconnect()
  document.removeEventListener('visibilitychange', foreground); window.removeEventListener('focus', foreground)
  window.removeEventListener('resize', closeMention)
  Object.values(imageUrls).forEach(URL.revokeObjectURL)
})
defineExpose({ toggleFilters: () => { filtersVisible.value = !filtersVisible.value } })
</script>

<style scoped>
.group-composer{position:relative}
.group-compose-tools{gap:2px!important;margin:0 0 4px!important}
.group-compose-tools .el-button{margin:0;color:#64748b;padding:5px 8px;height:28px}
.group-toolbar-spacer{flex:1}
.group-toolbar .el-button{padding:5px 7px;height:28px;color:#64748b}
.group-toolbar .group-follow.is-following{color:#b7791f}
.group-member-count{margin-left:5px;padding:1px 6px;border-radius:10px;background:#edf2f7;font-size:11px}
.group-composer :deep(.el-textarea__inner){box-shadow:none!important;border:0;background:transparent;padding:6px 8px;line-height:1.6}
.group-composer :deep(.el-textarea__inner:focus){box-shadow:none!important}
.group-mention-menu{position:absolute;z-index:20;display:flex;flex-direction:column;overflow:hidden;background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 8px 28px #0f172a26;padding:5px;box-sizing:border-box}
.group-mention-heading{display:flex;justify-content:space-between;gap:8px;padding:7px;color:#64748b;font-size:12px;flex-shrink:0}
.group-mention-heading span{font-size:10px;color:#94a3b8}
.group-mention-options{overflow:auto;min-height:0}
.group-mention-options button{display:flex;align-items:center;gap:9px;width:100%;border:0;border-radius:6px;padding:7px;background:white;color:#334155;text-align:left;cursor:pointer;font:inherit;overflow-wrap:anywhere}
.group-mention-options button.is-active{background:#eff6ff;color:#2563eb}
.group-mention-avatar{display:grid;place-items:center;flex-shrink:0;width:28px;height:28px;border-radius:50%;background:#e7eef9;color:#4b6b9e;font-size:12px}
.group-mention-empty{padding:15px;color:#94a3b8;text-align:center}
.annotation-group{display:flex;flex-direction:column;height:100%;min-height:0;background:#fff;color:#334155;font-size:13px}
.annotation-group--embedded{height:min(600px,65vh)}
.group-toolbar{display:flex;gap:5px;flex-wrap:wrap;padding:8px;border-bottom:1px solid #e2e8f0;flex-shrink:0}
.group-toolbar .el-button+.el-button{margin-left:0}.group-timeline{flex:1;min-height:0;overflow-y:auto;padding:12px;background:#f6f8fb;overflow-anchor:none}
.group-earlier{display:block;margin:auto}.group-message{margin:10px 0 14px;scroll-margin:25px}.group-message-meta{display:flex;gap:7px;align-items:center;font-size:12px;color:#64748b;margin-bottom:5px}.group-message-meta time{font-size:11px}.group-message--own .group-message-meta{justify-content:flex-end}.group-bubble{padding:9px 12px;background:white;border:1px solid #e2e8f0;border-radius:9px;max-width:94%;width:fit-content;overflow-wrap:anywhere}.group-message--own .group-bubble{margin-left:auto;background:#eaf3ff;border-color:#d5e6fc}.group-content{white-space:pre-wrap;line-height:1.6;margin:0;user-select:text}.group-mentions{color:#2563eb;font-size:12px}.group-message-actions{display:flex;gap:8px;opacity:0;margin-top:4px;flex-wrap:wrap}.group-message-actions .el-button{margin:0}.group-message:hover .group-message-actions,.group-message:focus-within .group-message-actions{opacity:1}.group-message--own .group-message-actions{justify-content:flex-end}.group-recalled{text-align:center;color:#94a3b8;font-size:12px}.group-reply{display:block;text-align:left;background:#f1f5f9;border:0;border-left:3px solid #94a3b8;color:#64748b;padding:6px;margin-bottom:7px;max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere;cursor:pointer}.group-file .el-image{max-width:240px;max-height:170px;display:block}.group-file .el-button{white-space:normal;text-align:left}.group-composer{flex-shrink:0;padding:9px;border-top:1px solid #e2e8f0;background:white}.group-compose-tools,.group-compose-footer{display:flex;align-items:center;gap:8px;margin:5px 0}.group-compose-footer{justify-content:space-between;font-size:11px;color:#94a3b8}.group-compose-reply{max-height:60px;overflow:auto;padding:6px;background:#f1f5f9;overflow-wrap:anywhere}.group-file-queue{max-height:85px;overflow:auto;font-size:12px}.group-file-queue>div{overflow-wrap:anywhere}.group-hint{font-size:12px;color:#64748b}.group-members{display:flex;gap:6px;flex-wrap:wrap;max-height:180px;overflow:auto;margin-bottom:12px}.group-filters{display:flex;flex-direction:column;gap:10px}.group-filters .el-date-editor{max-width:100%}.group-error{color:#b91c1c;font-size:12px;padding:3px 8px;overflow-wrap:anywhere}.group-new{align-self:center;flex-shrink:0}.group-message--highlight .group-bubble{outline:2px solid #409eff}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(hover:none){.group-message-actions{opacity:1}}@media(max-height:650px){.group-composer :deep(textarea){min-height:48px!important;height:48px}.group-file-queue{max-height:50px}}
</style>
<style>.annotation-members-popover{max-width:calc(100vw - 32px)!important;max-height:min(560px,calc(100vh - 120px));overflow-y:auto}</style>
