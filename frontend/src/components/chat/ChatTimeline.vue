<template>
    <div ref="list" class="group-timeline" @scroll="onScroll">
      <el-button v-if="hasEarlier" class="group-earlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="group-hint">正在加载消息…</div>
      <el-empty v-if="!loading && !messages.length" description="暂无消息，直接开始项目沟通" :image-size="50" />
      <template v-for="(message, index) in messages" :key="message.id">
      <div v-if="showMessageDates && (index === 0 || chatDayKey(message.createdAt) !== chatDayKey(messages[index - 1].createdAt))" class="group-date-divider">{{ formatMessageDay(message.createdAt) }}</div>
      <article :ref="el => observeMessage(el, message)" :data-message-id="message.id" :data-sequence="message.sequenceNo"
        class="group-message" :class="{ 'group-message--own': message.senderUserId === currentUserId, 'group-message--grouped': !chatGroupStart(message, messages[index - 1]), 'group-message--highlight': highlighted === message.id, 'group-message--mentioned': mentionsMe(message) }">
        <div class="group-message-meta"><el-checkbox v-if="!message.recalledAt && props.canAddToProgress && message.content" v-model="selected" :value="message.id" :label="message.id"><span class="sr-only">选择消息</span></el-checkbox><strong v-if="!message.recalledAt && message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])">{{ message.senderName }}</strong><time v-if="showMessageTime && timestampIndexes.has(index)" :title="showMessageTime && timestampIndexes.has(index) ? chatMessageTime(message.createdAt) : ''">{{ chatMessageTime(message.createdAt) }}</time></div>
        <ChatRecalledMessage v-if="message.recalledAt" :message="message" :can-reedit="recallDrafts?.canReedit(message)" @reedit="reeditMessage" />
        <template v-else>
          <span v-if="message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])" class="group-message-avatar" aria-hidden="true">{{ chatAvatarText(message.senderName) }}</span>
          <div class="group-message-main">
          <div class="group-bubble" tabindex="0" data-message-menu-anchor :title="showMessageTime && timestampIndexes.has(index) ? chatMessageTime(message.createdAt) : ''" @contextmenu="messageMenu.open($event,message)" @keydown="messageMenu.openKeyboard($event,message)">
            <button v-if="message.reply" class="group-reply" @click.stop="references.open(message.reply.id,$event)">{{ message.reply.senderName }}：{{ screenshotPreview(message.reply.content) }}</button>
            <AnnotationCreationCard v-if="message.contentJson?.type==='annotation_creation'" :card="message.contentJson" :chat-message-id="message.id" />
            <ScreenshotText v-else-if="screenshotIds(message.content).length" :text="message.content" :chat-message-id="message.id" />
            <p v-else-if="message.content" class="group-content" :class="{'has-references':message.reply || interactions.stats[message.id]?.replyCount}" :role="message.reply || interactions.stats[message.id]?.replyCount ? 'button' : undefined" :tabindex="message.reply || interactions.stats[message.id]?.replyCount ? 0 : undefined" @click="openReferences(message,$event)" @keydown.enter.stop="openReferences(message,$event)"><template v-for="(part, index) in mentionParts(message)" :key="index"><mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
            <el-tag v-if="message.topicPath" size="small" effect="plain" class="group-topic-label">{{ message.topicPath }}</el-tag>
            <div v-if="message.mentions?.some(m => !message.content?.includes(`@${m.mentionedUserName}`))" class="group-mentions">{{ message.mentions.filter(m => !message.content?.includes(`@${m.mentionedUserName}`)).map(m => `@${m.mentionedUserName}`).join(' ') }}</div>
            <div v-for="file in message.attachments" :key="file.id" class="group-file">
              <el-image v-if="file.contentType.startsWith('image/') && imageUrls[file.id]" :src="imageUrls[file.id]" :preview-src-list="[imageUrls[file.id]]" preview-teleported fit="contain" />
              <el-button v-else link type="primary" @click="download(file)">{{ file.originalName }} · {{ sizeLabel(file.fileSize) }}</el-button>
              <el-button v-if="file.contentType.startsWith('image/') && imageErrors[file.id]" link @click="loadImage(file)">重新加载图片</el-button>
            </div>
          </div>
          <button type="button" class="chat-message-more" aria-label="消息操作" @click="messageMenu.open($event,message)">⋯</button>
          </div>
          <ChatMessageActions :message="message" :current-user-id="currentUserId" :stats="interactions.stats[message.id]" :views-available="interactions.viewsAvailable.value" :acknowledging="ackBusy.has(message.id)" @reply="menuHandlers.reply" @acknowledge="confirmReceived" @references="(id,event)=>references.open(id,event)" />
        </template>
      </article>
      </template>
    </div>
    <ChatMessageContextMenu ref="messageMenu" :project-type="props.projectType" :project-id="props.projectId" :messages="messages" :current-user-id="currentUserId" :handlers="menuHandlers" :can-progress="props.canAddToProgress" :active="props.active" />
    <ChatMessageReferences ref="references" :project-id="props.projectId" :project-type="props.projectType" @locate="locate" />
</template>
<script setup>
import { screenshotPreview } from '@/utils/screenshotReferences'
import { computed, inject, nextTick, ref } from 'vue'
import ChatMessageContextMenu from './ChatMessageContextMenu.vue'
import AnnotationCreationCard from './AnnotationCreationCard.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { screenshotIds } from '@/utils/screenshotReferences'
import ChatMessageActions from './ChatMessageActions.vue'
import ChatMessageReferences from './ChatMessageReferences.vue'
import ChatRecalledMessage from './ChatRecalledMessage.vue'
import { chatAvatarText, chatDayKey, chatGroupStart, chatTimestampIndexes } from '@/utils/chatLayout'
import { useChatTimeDisplay } from '@/composables/useChatTimeDisplay'
const { formatMessageTime: chatMessageTime, formatMessageDay, showMessageTime, showMessageDates } = useChatTimeDisplay()
const { props, interactions, messages, list, hasEarlier, loadingEarlier, loadEarlier, loading, currentUserId, selected, highlighted, observeMessage, onScroll, formatDateTime, locate, imageUrls, imageErrors, sizeLabel, loadImage, download, copy, replyTo, favorite, acknowledge, recall, mentionsMe, mentionParts, input, toProgress, quoteMessage } = inject('chatController')
const timestampIndexes = computed(() => chatTimestampIndexes(messages.value))
const { recallDrafts, reeditMessage } = inject('chatController')
const messageMenu = ref(), references = ref(), ackBusy = ref(new Set())
function openReferences(message,event) { if(message.reply || interactions.stats[message.id]?.replyCount) references.value.open(message.reply?.id || message.id,event) }
async function confirmReceived(message) {
  if(ackBusy.value.has(message.id))return
  ackBusy.value.add(message.id)
  try { await acknowledge(message) } finally { ackBusy.value.delete(message.id) }
}
const menuHandlers = {
  copy, favorite, acknowledge, recall,
  reply: async message => { await quoteMessage(message) },
  progress: (message, excerpt) => toProgress([{ ...message, content: excerpt || message.content }]),
  select: message => { if (!selected.value.includes(message.id)) selected.value.push(message.id) },
}
</script>
<style scoped src="./chatConversation.css" />

<style scoped>
.group-message--mentioned .group-bubble{background:#eaf4ff;border-left:3px solid #60a5fa}.group-content mark{background:#ffe49b;color:#92400e;border-radius:3px}
.group-message-main{display:flex;align-items:center;gap:5px}.group-message--own .group-message-main{flex-direction:row-reverse}.group-message-main .group-bubble{margin-left:0;max-width:calc(94% - 35px)}.group-bubble:focus-visible{outline:2px solid var(--el-color-primary-light-5);outline-offset:2px}
.group-topic-label{margin-top:6px;max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere}
.group-message{position:relative;padding-left:42px;margin:16px 0}.group-message--own{padding-left:0;padding-right:0}.group-message--grouped{margin-top:-9px}.group-message-avatar{position:absolute;left:0;top:1px;display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#e4ecf8;color:#5274a5;font-size:13px}.group-date-divider{display:flex;align-items:center;justify-content:center;gap:16px;margin:22px 0;color:#94a3b8;font-size:11px}.group-date-divider::before,.group-date-divider::after{content:'';height:1px;width:48px;background:#e2e8f0}.group-message-meta{flex-wrap:wrap}.group-message-meta time{white-space:normal;overflow-wrap:anywhere}.group-message-main .group-bubble{max-width:calc(100% - 30px)}
</style>

<style scoped>.group-content.has-references{cursor:pointer}.group-content.has-references:hover{text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px}</style>
