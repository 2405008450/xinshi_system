<template>
    <div ref="composer" class="group-composer">
      <button type="button" class="chat-composer-resize" aria-label="调整输入区高度" title="拖动调整输入区高度" @pointerdown="start" @keydown="resizeByKeyboard" />
      <div v-if="replyTo" class="group-compose-reply">回复 {{ replyTo.senderName }}：{{ replyTo.content || '[附件]' }}<el-button link :disabled="sending || !!retryPayload" @click="replyTo=null">取消引用</el-button></div>
      <div class="group-compose-tools">
        <el-button v-if="!isDirect" text size="small" aria-label="提及用户" title="提及用户" :disabled="sending || !!retryPayload" @click="insertMention">@</el-button>
        <ChatTopicSelect v-model="sendTopicId" :disabled="sending || !!retryPayload" size="small" class="chat-send-topic" />
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" accept=".jpg,.jpeg,.png,.gif,.webp" :on-change="chooseFile"><el-button text size="small" :icon="Picture" :disabled="sending || !!retryPayload" aria-label="发送图片" title="发送图片" /></el-upload>
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" :on-change="chooseFile"><el-button text size="small" :icon="Paperclip" :disabled="sending || !!retryPayload" aria-label="发送文件" title="发送文件" /></el-upload>
      </div>
      <div v-if="files.length" class="group-file-queue"><div v-for="file in files" :key="file.key">{{ file.file.name }} · {{ file.status === 'uploading' ? '上传中…' : file.status === 'failed' ? '上传失败' : '待发送' }}<el-button v-if="file.status==='failed'" link @click="uploadFile(file)">重试</el-button><el-button link :disabled="sending || !!retryPayload" @click="removeFile(file)">移除</el-button><span v-if="file.error" class="group-error">{{ file.error }}</span></div></div>
      <el-input ref="input" v-model="content" type="textarea" :rows="3" :input-style="inputStyle" resize="none" maxlength="10000" :disabled="sending || !!retryPayload" :placeholder="isDirect ? '输入消息' : '输入消息，@ 提及用户'" :aria-expanded="mentionOpen" aria-autocomplete="list" :aria-controls="mentionOpen ? mentionListId : undefined" :aria-activedescendant="mentionOpen && mentionCandidates.length ? `${mentionListId}-${mentionIndex}` : undefined" @input="onInput" @click="onInput" @keyup.left="onInput" @keyup.right="onInput" @scroll.capture="closeMention" @blur="closeMention" @keydown="onKeydown" @compositionstart="composing=true; closeMention()" @compositionend="finishComposition" @paste="paste" />
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
import { inject, nextTick } from 'vue'
import { Paperclip, Picture } from '@element-plus/icons-vue'
import { useChatComposerHeight } from '@/composables/useChatComposerHeight'
import ChatTopicSelect from './ChatTopicSelect.vue'
const sendTopicId = inject('chatSendTopic')
const { inputStyle, start, resizeByKeyboard } = useChatComposerHeight()
const { props, composer, replyTo, sending, retryPayload, files, chooseFile, uploadFile, removeFile, input, content, mentionOpen, mentionListId, mentionCandidates, mentionIndex, onInput, closeMention, onKeydown, composing, finishComposition, paste, mentionMenu, mentionStyle, selectMention, cancelRetry, canSend, send, sendError, isDirect } = inject('chatController')
async function insertMention() {
  const textarea = input.value?.textarea
  const cursor = textarea?.selectionStart ?? content.value.length, end = textarea?.selectionEnd ?? cursor
  const text = `${cursor && !/\s$/.test(content.value.slice(0, cursor)) ? ' ' : ''}@`
  content.value = content.value.slice(0, cursor) + text + content.value.slice(end)
  await nextTick(); input.value?.focus(); textarea?.setSelectionRange(cursor + text.length, cursor + text.length); onInput()
}
</script>
<style scoped src="./chatConversation.css" />
<style scoped>.group-composer{margin:10px 12px 14px;border:1px solid #dfe5ee;border-radius:12px;padding:8px 10px;box-shadow:0 2px 6px #0f172a03}.group-composer:focus-within{border-color:var(--el-color-primary);box-shadow:0 0 0 2px var(--el-color-primary-light-9)}.group-compose-tools{flex-wrap:wrap;gap:6px}.chat-send-topic{width:min(180px,50%)}.group-compose-footer{justify-content:flex-end;gap:10px}.group-compose-footer>span{margin-right:auto}.chat-composer-resize{position:absolute;top:-5px;left:20%;width:60%;height:8px;padding:0;border:0;background:transparent;cursor:ns-resize;touch-action:none}.chat-composer-resize:focus-visible{outline:2px solid var(--el-color-primary)}</style>

