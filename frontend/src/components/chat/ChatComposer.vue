<template>
    <div ref="composer" class="group-composer">
      <div v-if="replyTo" class="group-compose-reply">回复 {{ replyTo.senderName }}：{{ replyTo.content || '[附件]' }}<el-button link :disabled="sending || !!retryPayload" @click="replyTo=null">取消引用</el-button></div>
      <div class="group-compose-tools">
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip" :on-change="chooseFile"><el-button text size="small" :icon="Paperclip" :disabled="sending || !!retryPayload" title="发送图片或文件">图片 / 文件</el-button></el-upload>
      </div>
      <div v-if="files.length" class="group-file-queue"><div v-for="file in files" :key="file.key">{{ file.file.name }} · {{ file.status === 'uploading' ? '上传中…' : file.status === 'failed' ? '上传失败' : '待发送' }}<el-button v-if="file.status==='failed'" link @click="uploadFile(file)">重试</el-button><el-button link :disabled="sending || !!retryPayload" @click="removeFile(file)">移除</el-button><span v-if="file.error" class="group-error">{{ file.error }}</span></div></div>
      <el-input ref="input" v-model="content" type="textarea" :rows="3" resize="none" maxlength="10000" :disabled="sending || !!retryPayload" :placeholder="isDirect ? '输入消息' : '输入消息，@ 提及用户'" :aria-expanded="mentionOpen" aria-autocomplete="list" :aria-controls="mentionOpen ? mentionListId : undefined" :aria-activedescendant="mentionOpen && mentionCandidates.length ? `${mentionListId}-${mentionIndex}` : undefined" @input="onInput" @click="onInput" @keyup.left="onInput" @keyup.right="onInput" @scroll.capture="closeMention" @blur="closeMention" @keydown="onKeydown" @compositionstart="composing=true; closeMention()" @compositionend="finishComposition" @paste="paste" />
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
</template>
<script setup>
import { inject } from 'vue'
import { Paperclip } from '@element-plus/icons-vue'
const { props, composer, replyTo, sending, retryPayload, files, chooseFile, uploadFile, removeFile, input, content, mentionOpen, mentionListId, mentionCandidates, mentionIndex, onInput, closeMention, onKeydown, composing, finishComposition, paste, mentionMenu, mentionStyle, selectMention, cancelRetry, canSend, send, sendError, isDirect } = inject('chatController')
</script>
<style scoped src="./chatConversation.css" />

