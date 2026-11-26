<template>
    <div ref="list" class="group-timeline" @scroll="onScroll">
      <div class="chat-timeline-content" style="display: flow-root">
      <el-button v-if="hasEarlier" class="group-earlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="group-hint">正在加载消息…</div>
      <el-empty v-if="!loading && !messages.length" description="暂无消息，直接开始项目沟通" :image-size="50" />
      <template v-for="(message, index) in messages" :key="message.id">
      <div v-if="showMessageDates && (index === 0 || chatDayKey(message.createdAt) !== chatDayKey(messages[index - 1].createdAt))" class="group-date-divider"><span>{{ formatMessageDay(message.createdAt) }}</span></div>
      <article :ref="el => observeMessage(el, message)" :data-message-id="message.id" :data-sequence="message.sequenceNo"
        class="group-message" :class="{ 'group-message--own': message.senderUserId === currentUserId, 'group-message--grouped': !chatGroupStart(message, messages[index - 1]), 'group-message--highlight': highlighted === message.id, 'group-message--mentioned': mentionsMe(message), 'group-message--sending': message.optimisticStatus === 'sending', 'group-message--failed': message.optimisticStatus === 'failed' }">
        <div class="group-message-meta"><el-checkbox v-if="!message.recalledAt && !message.optimisticStatus && props.canAddToProgress && message.content" v-model="selected" :value="message.id" :label="message.id"><span class="sr-only">选择消息</span></el-checkbox><strong v-if="!message.recalledAt && message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])">{{ message.senderName }}</strong><time v-if="showMessageTime && timestampIndexes.has(index)" :title="showMessageTime && timestampIndexes.has(index) ? chatMessageTime(message.createdAt) : ''">{{ chatMessageTime(message.createdAt) }}</time></div>
        <ChatRecalledMessage v-if="message.recalledAt" :message="message" :can-reedit="recallDrafts?.canReedit(message)" @reedit="reeditMessage" />
        <template v-else>
          <span v-if="message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])" class="group-message-avatar" aria-hidden="true">{{ chatAvatarText(message.senderName) }}</span>
          <div class="group-message-main">
          <div class="group-bubble" tabindex="0" data-message-menu-anchor :title="showMessageTime && timestampIndexes.has(index) ? chatMessageTime(message.createdAt) : ''" @contextmenu="!message.optimisticStatus && messageMenu.open($event,message)" @keydown="!message.optimisticStatus && messageMenu.openKeyboard($event,message)">
            <blockquote v-if="message.reply" class="group-reply"><span class="chat-quote-clamp">{{ message.reply.senderName }}：{{ screenshotPreview(message.reply.content) }}</span></blockquote>
            <ChatMessageInlineEditor v-if="editingMessageId === message.id" :message="message" :saving="editingSaving" :error="editingError" @save="payload => saveEdit(message, payload)" @cancel="cancelEdit" />
            <template v-else>
              <AnnotationCreationCard v-if="message.contentJson?.type==='annotation_creation'" :card="message.contentJson" :chat-message-id="message.id" />
              <ScreenshotText v-else-if="screenshotIds(message.content).length" :text="message.content" :chat-message-id="message.id" />
              <p v-else-if="message.content" class="group-content"><template v-for="(part, index) in mentionParts(message)" :key="index"><mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
            </template>
            <span v-if="message.editedAt && editingMessageId !== message.id" class="chat-edited-tag" :title="`已编辑于 ${chatMessageTime(message.editedAt)}`">已编辑</span>
            <el-tag v-if="message.topicPath" size="small" effect="plain" class="group-topic-label">{{ message.topicPath }}</el-tag>
            <div v-if="message.mentions?.some(m => !message.content?.includes(`@${m.mentionedUserName}`))" class="group-mentions">{{ message.mentions.filter(m => !message.content?.includes(`@${m.mentionedUserName}`)).map(m => `@${m.mentionedUserName}`).join(' ') }}</div>
            <div v-for="file in message.attachments" :key="file.id" class="group-file">
              <el-image v-if="file.contentType.startsWith('image/') && imageUrls[file.id]" :src="imageUrls[file.id]" :preview-src-list="[imageUrls[file.id]]" preview-teleported fit="contain" />
              <ChatMediaAttachment v-else-if="file.contentType.startsWith('audio/') || file.contentType.startsWith('video/')" :key="`${props.projectType}:${props.projectId}:${file.id}`" :file="file" :fetch-blob="fileBlob" :size-label="sizeLabel" :active="props.active" />
              <el-button v-else link type="primary" @click="download(file)">{{ file.originalName }} · {{ sizeLabel(file.fileSize) }}</el-button>
              <el-button v-if="file.contentType.startsWith('image/') && imageErrors[file.id]" link @click="loadImage(file)">重新加载图片</el-button>
            </div>
          </div>
          <button v-if="!message.optimisticStatus" type="button" class="chat-message-more" aria-label="消息操作" @click="messageMenu.open($event,message)">⋯</button>
          <span v-else-if="message.optimisticStatus === 'sending'" class="chat-optimistic-sending" role="status">发送中…</span>
          <span v-else-if="message.optimisticStatus === 'failed'" class="chat-optimistic-failed" role="alert" :title="message.optimisticError || '发送失败'">
            <span>发送失败</span>
            <button type="button" class="chat-optimistic-action" @click="retryOptimisticMessage(message)">重试</button>
            <button type="button" class="chat-optimistic-action is-muted" @click="removeOptimisticMessage(message)">移除</button>
          </span>
          </div>
          <ChatMessageActions :message="message" :current-user-id="currentUserId" :stats="interactions.stats[message.id]" :views-available="interactions.viewsAvailable.value" :acknowledging="ackBusy.has(message.id)" @reply="menuHandlers.reply" @acknowledge="confirmReceived" @references="(id,event)=>references.open(id,event)" />
        </template>
      </article>
      </template>
      </div>
    </div>
    <ChatMessageContextMenu ref="messageMenu" :project-type="props.projectType" :project-id="props.projectId" :messages="messages" :current-user-id="currentUserId" :handlers="menuHandlers" :can-progress="props.canAddToProgress" :active="props.active" />
    <ChatMessageReferences ref="references" :project-id="props.projectId" :project-type="props.projectType" @locate="locate" />
</template>
<script setup>
import ChatMediaAttachment from './ChatMediaAttachment.vue'
import { screenshotPreview } from '@/utils/screenshotReferences'
import { computed, inject, nextTick, ref } from 'vue'
import ChatMessageContextMenu from './ChatMessageContextMenu.vue'
import AnnotationCreationCard from './AnnotationCreationCard.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { screenshotIds } from '@/utils/screenshotReferences'
import ChatMessageActions from './ChatMessageActions.vue'
import ChatMessageReferences from './ChatMessageReferences.vue'
import ChatRecalledMessage from './ChatRecalledMessage.vue'
import ChatMessageInlineEditor from './ChatMessageInlineEditor.vue'
import { chatAvatarText, chatDayKey, chatGroupStart, chatTimestampIndexes } from '@/utils/chatLayout'
import { useChatTimeDisplay } from '@/composables/useChatTimeDisplay'
const { formatMessageTime: chatMessageTime, formatMessageDay, showMessageTime, showMessageDates } = useChatTimeDisplay()
const { props, interactions, messages, list, hasEarlier, loadingEarlier, loadEarlier, loading, currentUserId, selected, highlighted, observeMessage, onScroll, formatDateTime, locate, imageUrls, imageErrors, sizeLabel, loadImage, fileBlob, download, copy, replyTo, favorite, acknowledge, recall, mentionsMe, mentionParts, input, toProgress, quoteMessage } = inject('chatController')
const timestampIndexes = computed(() => chatTimestampIndexes(messages.value))
const { recallDrafts, reeditMessage, editingMessageId, editingSaving, editingError, startEdit, cancelEdit, saveEdit, retryOptimisticMessage, removeOptimisticMessage } = inject('chatController')
const messageMenu = ref(), references = ref(), ackBusy = ref(new Set())
async function confirmReceived(message) {
  if(ackBusy.value.has(message.id))return
  ackBusy.value.add(message.id)
  try { await acknowledge(message) } finally { ackBusy.value.delete(message.id) }
}
const menuHandlers = {
  copy, favorite, acknowledge, edit: startEdit, recall,
  reply: async message => { await quoteMessage(message) },
  progress: (message, excerpt) => toProgress([{ ...message, content: excerpt || message.content }]),
  select: message => { if (!selected.value.includes(message.id)) selected.value.push(message.id) },
}
</script>
<style scoped src="./chatConversation.css" />

<style scoped>
.group-message--mentioned .group-bubble{background:var(--chat-bubble-mention-bg,#fef9ec);border-color:#f3d99b;border-left:3px solid var(--chat-bubble-mention-accent,#d97706)}.group-content mark{background:#fef3c7;color:#92400e;border-radius:4px;padding:0 3px;font-weight:500}
.group-message-main{display:flex;align-items:center;gap:6px}.group-message--own .group-message-main{flex-direction:row-reverse}.group-message-main .group-bubble{margin-left:0;max-width:min(680px,calc(100% - 34px))}.group-bubble:focus-visible{outline:2px solid var(--el-color-primary-light-5);outline-offset:2px}
.group-topic-label{margin-top:6px;max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere}
.chat-edited-tag{display:inline-block;margin-top:4px;font-size:11px;color:#94a3b8}
.group-message--sending .group-bubble{opacity:.9}
.group-message--failed .group-bubble{border-color:#fca5a5}
.chat-optimistic-sending{font-size:11px;color:#94a3b8;white-space:nowrap;opacity:0;animation:chat-opt-fade .18s ease .4s forwards}
.chat-optimistic-failed{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#dc2626;white-space:nowrap}
.chat-optimistic-action{border:0;background:transparent;padding:0 2px;font:inherit;color:#2563eb;cursor:pointer}
.chat-optimistic-action:hover{text-decoration:underline}
.chat-optimistic-action.is-muted{color:#64748b}
@keyframes chat-opt-fade{to{opacity:1}}
.group-message{position:relative;padding-left:42px;margin:14px 0}.group-message--own{padding-left:0;padding-right:0}.group-message--grouped{margin-top:-6px}.group-message-avatar{position:absolute;left:0;top:1px;display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#e3ebf5;color:#3b526b;font-size:12.5px;font-weight:600;border:1px solid #d5e0ee}.group-date-divider{display:flex;align-items:center;justify-content:center;margin:18px 0}.group-date-divider>span{padding:2px 10px;border-radius:10px;background:#e8edf4;color:#64748b;font-size:11px;line-height:1.5}.group-message-meta{flex-wrap:wrap}.group-message-meta time{white-space:normal;overflow-wrap:anywhere}
</style>

<style scoped>
/* 手机端：气泡与背景更接近微信，自己发送的消息为绿色。 */
@media (max-width: 640px) {
  .group-timeline{padding:10px 10px 6px;background:var(--chat-stage-bg,#f1f5f9)}
  .group-bubble{padding:8px 11px;border:0;border-radius:6px;font-size:15px}
  .group-message--own .group-bubble{background:var(--color-primary-soft,#e2e8f0);border-color:var(--color-primary-soft,#e2e8f0)}
  .group-message--mentioned .group-bubble{background:#fff8db;border-left:3px solid #e9ac24}
  .group-message-main .group-bubble{max-width:calc(100% - 56px)}
}
</style>

<style scoped src="./chatQuotes.css" />
