<template>
    <div ref="composer" class="group-composer">
      <button type="button" class="chat-composer-resize" aria-label="调整输入区高度" title="拖动调整输入区高度" @pointerdown="start" @keydown="resizeByKeyboard" />
      <div v-if="replyTo" class="group-compose-reply">回复 {{ replyTo.senderName }}：{{ screenshotPreview(replyTo.content) || '[附件]' }}<el-button link :disabled="sending || !!retryPayload" @click="replyTo=null">取消引用</el-button></div>
      <div class="group-compose-tools">
        <el-button v-if="!isDirect" text size="small" aria-label="提及用户" title="提及用户" :disabled="sending || !!retryPayload" @click="insertMention">@</el-button>
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" accept=".jpg,.jpeg,.png,.gif,.webp" :on-change="chooseFile"><el-button text size="small" :icon="Picture" :disabled="sending || !!retryPayload" aria-label="发送图片" title="发送图片" /></el-upload>
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" :on-change="chooseFile"><el-button text size="small" :icon="Paperclip" :disabled="sending || !!retryPayload" aria-label="发送文件" title="发送文件" /></el-upload>
      </div>
      <div v-if="files.length" class="group-file-queue"><div v-for="file in files" :key="file.key">{{ file.file.name }} · {{ file.status === 'uploading' ? '上传中…' : file.status === 'failed' ? '上传失败' : '待发送' }}<el-button v-if="file.status==='failed'" link @click="uploadFile(file)">重试</el-button><el-button link :disabled="sending || !!retryPayload" @click="removeFile(file)">移除</el-button><span v-if="file.error" class="group-error">{{ file.error }}</span></div></div>
      <el-input ref="input" v-model="content" @uploading-change="screenshotUploading=$event" type="textarea" :rows="3" :input-style="inputStyle" resize="none" maxlength="10000" :disabled="sending || !!retryPayload" :placeholder="isDirect ? '输入消息' : '输入消息，@ 提及用户'" :aria-expanded="mentionOpen" aria-autocomplete="list" :aria-controls="mentionOpen ? mentionListId : undefined" :aria-activedescendant="mentionOpen && mentionCandidates.length ? `${mentionListId}-${mentionIndex}` : undefined" @input="onInput" @click="onInput" @keyup.left="onInput" @keyup.right="onInput" @scroll.capture="closeMention" @blur="onMentionBlur" @keydown="onKeydown" @compositionstart="composing=true; closeMention()" @compositionend="finishComposition" @paste="paste" />
      <div v-if="mentionOpen" :id="mentionListId" ref="mentionMenu" class="group-mention-menu" :style="mentionStyle" role="listbox" aria-label="选择提及用户" @mousedown="keepMentionFocus">
        <div class="group-mention-heading">提及用户<span>↑↓ 选择 · Enter 确认</span></div>
        <el-input v-model="mentionQuery" class="group-mention-search" clearable placeholder="搜索要 @ 的人员" aria-label="搜索要提及的人员" @input="mentionIndex = 0" @blur="onMentionBlur" @keydown="onKeydown" />
        <div class="group-mention-options">
          <template v-for="(user, index) in mentionCandidates" :key="user.id">
            <div v-if="!index || user.outside !== mentionCandidates[index - 1].outside" class="group-mention-section" :class="{ 'is-outside': user.outside }">{{ user.outside ? '未参与人员 · 发送后自动加入' : '群组参与人' }}</div>
            <button :id="`${mentionListId}-${index}`" type="button" role="option" :aria-selected="index === mentionIndex" :class="{ 'is-active': index === mentionIndex, 'is-outside': user.outside }" @mouseenter="mentionIndex=index" @click="selectMention(user)"><span class="group-mention-avatar">{{ user.name.slice(0, 1) }}</span><span>{{ user.name }}</span><ChatDesktopPresence :online="desktopPresence[user.id]" :loading="desktopPresenceLoading" /><small v-if="user.outside">邀请入群</small></button>
          </template>
          <div v-if="!mentionCandidates.length" class="group-mention-empty">没有匹配的用户</div>
        </div>
      </div>
      <div class="group-compose-footer"><span>Enter发送 · Shift+Enter换行</span><el-button v-if="retryPayload" size="small" @click="cancelRetry">继续编辑</el-button><el-button type="primary" size="small" :loading="sending" :disabled="!canSend" @click="send">{{ retryPayload ? '发送失败，重试' : '发送' }}</el-button></div>
      <div v-if="sendError" class="group-error" role="alert">{{ sendError }}</div>
    </div>
</template>
<script setup>
import { screenshotPreview } from '@/utils/screenshotReferences'
import { computed, inject, nextTick } from 'vue'
import ChatDesktopPresence from './ChatDesktopPresence.vue'
import { useDesktopPresence } from '@/composables/useDesktopPresence'
import { Paperclip, Picture } from '@element-plus/icons-vue'
import { useChatComposerHeight } from '@/composables/useChatComposerHeight'
const { inputStyle, start, resizeByKeyboard } = useChatComposerHeight()
const { props, composer, replyTo, sending, retryPayload, files, chooseFile, uploadFile, removeFile, input, content, mentionOpen, mentionListId, mentionQuery, mentionCandidates, mentionIndex, onInput, closeMention, onKeydown, composing, finishComposition, paste, screenshotUploading, mentionMenu, mentionStyle, selectMention, cancelRetry, canSend, send, sendError, isDirect } = inject('chatController')
const { statuses: desktopPresence, loading: desktopPresenceLoading } = useDesktopPresence(computed(() => mentionCandidates.value.map(user => user.id)), computed(() => props.active && mentionOpen.value))
function keepMentionFocus(event) {
  // 搜索框需要获得焦点；候选按钮保留输入光标，确保选择时替换正确的 @ 文本。
  if (!event.target.closest('input')) event.preventDefault()
}
function onMentionBlur(event) {
  if (!mentionMenu.value?.contains(event.relatedTarget)) closeMention()
}
async function insertMention() {
  const textarea = input.value?.textarea
  const cursor = textarea?.selectionStart ?? content.value.length, end = textarea?.selectionEnd ?? cursor
  const text = `${cursor && !/\s$/.test(content.value.slice(0, cursor)) ? ' ' : ''}@`
  content.value = content.value.slice(0, cursor) + text + content.value.slice(end)
  await nextTick(); input.value?.focus(); textarea?.setSelectionRange(cursor + text.length, cursor + text.length); onInput()
}
</script>
<style scoped src="./chatConversation.css" />
<style scoped>.group-composer{margin:10px 12px 14px;border:1px solid #dfe5ee;border-radius:12px;padding:8px 10px;box-shadow:0 2px 6px #0f172a03}.group-composer:focus-within{border-color:var(--el-color-primary);box-shadow:0 0 0 2px var(--el-color-primary-light-9)}.group-compose-tools{flex-wrap:wrap;gap:6px}.group-compose-footer{justify-content:flex-end;gap:10px}.group-compose-footer>span{margin-right:auto}.chat-composer-resize{position:absolute;top:-5px;left:20%;width:60%;height:8px;padding:0;border:0;background:transparent;cursor:ns-resize;touch-action:none}.chat-composer-resize:focus-visible{outline:2px solid var(--el-color-primary)}.group-mention-search{flex-shrink:0;margin-bottom:5px}.group-mention-section{position:sticky;top:0;padding:7px;background:#eff6ff;color:#1d4ed8;font-size:11px;font-weight:600;border-bottom:1px solid #dbeafe}.group-mention-section.is-outside{background:#fff7ed;color:#9a3412;border-top:2px solid #fed7aa;border-bottom-color:#ffedd5}.group-mention-options button small{margin-left:auto;flex:none;color:#9a3412;font-size:10px}
</style>

