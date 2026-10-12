<template>
    <div ref="list" class="group-timeline" @scroll="onScroll">
      <el-button v-if="hasEarlier" class="group-earlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="group-hint">正在加载消息…</div>
      <el-empty v-if="!loading && !messages.length" description="暂无消息，直接开始项目沟通" :image-size="50" />
      <template v-for="(message, index) in messages" :key="message.id">
      <div v-if="index === 0 || chatDayKey(message.createdAt) !== chatDayKey(messages[index - 1].createdAt)" class="group-date-divider">{{ chatDateLabel(message.createdAt, new Date(), true) }}</div>
      <article :ref="el => observeMessage(el, message)" :data-message-id="message.id" :data-sequence="message.sequenceNo"
        class="group-message" :class="{ 'group-message--own': message.senderUserId === currentUserId, 'group-message--grouped': !chatGroupStart(message, messages[index - 1]), 'group-message--highlight': highlighted === message.id, 'group-message--mentioned': mentionsMe(message) }">
        <div v-if="message.recalledAt" class="group-recalled">{{ message.recallLabel }}</div>
        <template v-else>
          <span v-if="message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])" class="group-message-avatar" aria-hidden="true">{{ chatAvatarText(message.senderName) }}</span>
          <div v-if="chatGroupStart(message, messages[index - 1]) || props.canAddToProgress" class="group-message-meta"><el-checkbox v-if="props.canAddToProgress && message.content" v-model="selected" :value="message.id" :label="message.id"><span class="sr-only">选择消息</span></el-checkbox><strong v-if="message.senderUserId !== currentUserId && chatGroupStart(message, messages[index - 1])">{{ message.senderName }}</strong><time :title="formatDateTime(message.createdAt)">{{ chatClock(message.createdAt) }}</time></div>
          <div class="group-message-main">
          <div class="group-bubble" tabindex="0" data-message-menu-anchor :title="formatDateTime(message.createdAt)" @contextmenu="messageMenu.open($event,message)" @keydown="messageMenu.openKeyboard($event,message)">
            <button v-if="message.reply" class="group-reply" @click="locate(message.reply.id)">{{ message.reply.senderName }}：{{ message.reply.content }}</button>
            <p v-if="message.content" class="group-content"><template v-for="(part, index) in mentionParts(message)" :key="index"><mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
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
        </template>
      </article>
      </template>
    </div>
    <ChatMessageContextMenu ref="messageMenu" :messages="messages" :current-user-id="currentUserId" :handlers="menuHandlers" :can-progress="props.canAddToProgress" :active="props.active" />
</template>
<script setup>
import { inject, nextTick, ref } from 'vue'
import ChatMessageContextMenu from './ChatMessageContextMenu.vue'
import { chatAvatarText, chatDayKey, chatDateLabel, chatClock, chatGroupStart } from '@/utils/chatLayout'
const { props, messages, list, hasEarlier, loadingEarlier, loadEarlier, loading, currentUserId, selected, highlighted, observeMessage, onScroll, formatDateTime, locate, imageUrls, imageErrors, sizeLabel, loadImage, download, copy, replyTo, favorite, acknowledge, recall, mentionsMe, mentionParts, input, toProgress } = inject('chatController')
const messageMenu = ref()
const menuHandlers = {
  copy, favorite, acknowledge, recall,
  reply: async message => { replyTo.value = message; await nextTick(); input.value?.focus() },
  progress: (message, excerpt) => toProgress([{ ...message, content: excerpt || message.content }]),
  select: message => { if (!selected.value.includes(message.id)) selected.value.push(message.id) },
}
</script>
<style scoped src="./chatConversation.css" />

<style scoped>
.group-message--mentioned .group-bubble{background:#fff8db;border-left:3px solid #e9ac24}.group-content mark{background:#ffe49b;color:#92400e;border-radius:3px}
.group-message-main{display:flex;align-items:center;gap:5px}.group-message--own .group-message-main{flex-direction:row-reverse}.group-message-main .group-bubble{margin-left:0;max-width:calc(94% - 35px)}.group-bubble:focus-visible{outline:2px solid var(--el-color-primary-light-5);outline-offset:2px}
.group-topic-label{margin-top:6px;max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere}
.group-message{position:relative;padding-left:42px;margin:16px 0}.group-message--own{padding-left:0;padding-right:0}.group-message--grouped{margin-top:-9px}.group-message-avatar{position:absolute;left:0;top:1px;display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#e4ecf8;color:#5274a5;font-size:13px}.group-date-divider{display:flex;align-items:center;justify-content:center;gap:16px;margin:22px 0;color:#94a3b8;font-size:11px}.group-date-divider::before,.group-date-divider::after{content:'';height:1px;width:48px;background:#e2e8f0}.group-message--own .group-message-meta time{opacity:0}.group-message--own:hover .group-message-meta time,.group-message--own:focus-within .group-message-meta time{opacity:1}.group-message-main .group-bubble{max-width:calc(100% - 30px)}
</style>
