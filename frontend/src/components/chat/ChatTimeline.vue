<template>
    <div ref="list" class="group-timeline" @scroll="onScroll">
      <el-button v-if="hasEarlier" class="group-earlier" link :loading="loadingEarlier" @click="loadEarlier">加载更早的消息</el-button>
      <div v-if="loading" class="group-hint">正在加载消息…</div>
      <el-empty v-if="!loading && !messages.length" description="暂无消息，直接开始项目沟通" :image-size="50" />
      <article v-for="message in messages" :key="message.id" :ref="el => observeMessage(el, message)" :data-message-id="message.id" :data-sequence="message.sequenceNo"
        class="group-message" :class="{ 'group-message--own': message.senderUserId === currentUserId, 'group-message--highlight': highlighted === message.id, 'group-message--mentioned': mentionsMe(message) }">
        <div v-if="message.recalledAt" class="group-recalled">{{ message.recallLabel }}</div>
        <template v-else>
          <div class="group-message-meta"><el-checkbox v-if="props.canAddToProgress && message.content" v-model="selected" :value="message.id" :label="message.id"><span class="sr-only">选择消息</span></el-checkbox><strong>{{ message.senderName }}</strong><time>{{ formatDateTime(message.createdAt) }}</time></div>
          <div class="group-bubble">
            <button v-if="message.reply" class="group-reply" @click="locate(message.reply.id)">{{ message.reply.senderName }}：{{ message.reply.content }}</button>
            <p v-if="message.content" class="group-content" @contextmenu="selectionMessage=message"><template v-for="(part, index) in mentionParts(message)" :key="index"><mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
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
</template>
<script setup>
import { inject } from 'vue'
import { Paperclip } from '@element-plus/icons-vue'
const { props, messages, list, hasEarlier, loadingEarlier, loadEarlier, loading, currentUserId, selected, selectionMessage, highlighted, observeMessage, onScroll, formatDateTime, locate, imageUrls, imageErrors, sizeLabel, loadImage, download, copy, replyTo, favorite, acknowledge, recall, mentionsMe, mentionParts } = inject('chatController')
</script>
<style scoped src="./chatConversation.css" />

<style scoped>
.group-message--mentioned .group-bubble{background:#fff8db;border-left:3px solid #e9ac24}.group-content mark{background:#ffe49b;color:#92400e;border-radius:3px}
</style>
